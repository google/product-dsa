# coding=utf-8
# Copyright 2021 Google LLC..
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# python3
"""Cloud Environment setup module for initial installation.

This module automates the following steps:
  1. Create GMC BigQuery Data Transfer
  2. Setup tables and views in BigQuery
"""

import logging
from typing import NamedTuple, Dict, Union, List
from googleapiclient.discovery import build
from google.cloud import storage, exceptions
from pprint import pprint
# if you're getting an error on the next line "ModuleNotFound",
# make sure you define env var PYTHONPATH="."
from common import auth, config_utils, cloud_utils, bigquery_utils
from install import cloud_data_transfer

# Set logging level.
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)


def execute_queries(bigquery_util: bigquery_utils.CloudBigQueryUtils,
                    config: config_utils.Config):
  logging.info('Creating solution specific views.')
  # Sql files to be executed in a specific order. The prefix "scripts" should be omitted.
  sql_files = [
      'filter-products.sql',
  ]
  bigquery_util.execute_queries(sql_files, config.dataset_id,
                                config.dataset_location, config.merchant_id)


def set_permission_on_drive(fileId, email, credentials):
  driveAPI = build('drive', 'v3', credentials=credentials)
  access = driveAPI.permissions().create(
      fileId=fileId,
      body={
          'type': 'user',
          'role': 'writer',
          'emailAddress': email
      },
      fields='id',
      #transferOwnership=True  - use it if you want to transfer ownership (change role  to 'owner' then, and comment out sendNotificationEmail=False)
      sendNotificationEmail=False).execute()


def create_page_feed_spreadsheet(config: config_utils.Config,
                                 credentials) -> bool:
  if config.page_feed_spreadsheetid:
    logging.info('Skipped spreadsheet creation as config contains a docid: ' +
                 config.page_feed_spreadsheetid)
    return False
  logging.info('Creating a spreadsheet for page feed data')
  logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)
  sheetsAPI = build('sheets', 'v4', credentials=credentials)
  result = sheetsAPI.spreadsheets().create(
      body={
          "sheets": [{
              "properties": {
                  "title": "Main"
              }
          }],
          "properties": {
              "title":
                  f"Product page feed (GMC {config.merchant_id} / GCP project {config.project_id})"
          }
      }).execute()
  config.page_feed_spreadsheetid = result['spreadsheetId']
  logging.info('Created spreadsheet: ' + config.page_feed_spreadsheetid)
  # set permission on the created spreadsheet for GAE default service account
  saEmail = f"{config.project_id}@appspot.gserviceaccount.com"
  set_permission_on_drive(config.page_feed_spreadsheetid, saEmail, credentials)

  return True


def backup_config(config_file_name: str, config: config_utils.Config,
                  credentials):
  if not config_file_name.startswith('gs://'):
    storage_client = storage.Client(project=config.project_id,
                                    credentials=credentials)
    # create (or reuse) a GCS bucket and put the config there
    bucket_name = f'{config.project_id}-setup'
    try:
      bucket = storage_client.get_bucket(bucket_name)
    except exceptions.NotFound:
      bucket = storage_client.create_bucket(bucket_name)
    blob = bucket.blob(config_file_name)
    blob.upload_from_filename(config_file_name)
    logging.info(
        f'config file ({config_file_name}) has been copied to gs://{bucket_name}'
    )


def enable_apis(apis: List[str], config: config_utils.Config, credentials):
  """Enables multiple Cloud APIs for a GCP project.

  Args:
    apis: The list of APIs to be enabled.

  Raises:
      Error: If the request was not processed successfully.
  """
  parent = f'projects/{config.project_id}'
  request_body = {'serviceIds': apis}
  client = build('serviceusage',
                 'v1',
                 credentials=credentials,
                 cache_discovery=False)
  operation = client.services().batchEnable(parent=parent,
                                            body=request_body).execute()
  cloud_utils.wait_for_operation(client.operations(), operation)


def create_scheduler_job(config: config_utils.Config, credentials):
  from google.cloud import scheduler

  client = scheduler.CloudSchedulerClient(credentials=credentials)
  parent = f"projects/{config.project_id}/locations/{config.scheduler_location}"
  job = {
      'app_engine_http_target': {
          'relative_uri': '/pagefeed/update',
          'http_method': 1,
          #'body': 'Hello World'.encode()
      },
      # TODO: set current time in UTC
      'schedule': '0 * * * *',
      'time_zone': 'America/Los_Angeles'
  }
  response = client.create_job(request={"parent": parent, "job": job})
  logging.info(f'Created Scheduler job ${response.name}')


def main():
  args = config_utils.parse_arguments()

  config = config_utils.get_config(args)
  pprint(vars(config))

  credentials = auth.get_credentials(args)

  logging.info('Enabling apis')
  enable_apis([
      'bigquery.googleapis.com', 'bigquerydatatransfer.googleapis.com',
      'sheets.googleapis.com', 'drive.googleapis.com',
      'cloudscheduler.googleapis.com'
  ], config, credentials)
  logging.info('apis have been enabled')

  logging.info('Creating %s dataset.', config.dataset_id)
  bigquery_client = bigquery_utils.CloudBigQueryUtils(config.project_id,
                                                      credentials)
  bigquery_client.create_dataset_if_not_exists(config.dataset_id,
                                               config.dataset_location)

  data_transfer = cloud_data_transfer.CloudDataTransferUtils(
      config.project_id, config.dataset_location, credentials)
  merchant_center_config = data_transfer.create_merchant_center_transfer(
      config.merchant_id, config.dataset_id)

  # ads_config = data_transfer.create_google_ads_transfer(ads_customer_id, args.dataset_id)
  try:
    logging.info('Checking the GMC data transfer status.')
    data_transfer.wait_for_transfer_completion(merchant_center_config)
    logging.info('The GMC data have been successfully transferred.')
  except cloud_data_transfer.DataTransferError:
    logging.error('If you have just created GMC transfer - you may need to'
                  'wait for up to 90 minutes before the data of your Merchant'
                  'account are prepared and available for the transfer.')
    raise

  # logging.info('Checking the Google Ads data transfer status.')
  # data_transfer.wait_for_transfer_completion(ads_config)
  # logging.info('The Google Ads data have been successfully transferred.')

  execute_queries(bigquery_client, config)

  # creating a spreadsheet for page feed data
  created = create_page_feed_spreadsheet(config, credentials)

  config_file_name = args.config or 'config.yaml'
  if created:
    # overwrite config file with new data
    config_utils.save_config(config, config_file_name)

  # As we could have modified the config (e.g. put a spreadsheet id),
  # we need to save it to a well-known location - GCS bucket {project_id}-setup:
  backup_config(config_file_name, config, credentials)

  # create a Scheduler job to execute API /pagefeed/update to update the spreadsheet with pagefeed data
  create_scheduler_job(config, credentials)

  logging.info('installation is complete!')


if __name__ == '__main__':
  main()
