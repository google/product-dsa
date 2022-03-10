# coding=utf-8
# Copyright 2022 Google LLC..
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
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
import argparse
import os
from typing import NamedTuple, Dict, Union, List
from google.auth import credentials
from google.cloud.bigquery_datatransfer_v1.types import TransferConfig
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from google.cloud import storage, pubsub_v1, exceptions
from google.api_core import exceptions
from pprint import pprint
# if you're getting an error on the next line "ModuleNotFound",
# make sure you define env var PYTHONPATH="."
from common import auth, config_utils, cloud_utils, bigquery_utils, file_utils
from install import cloud_data_transfer

# Set logging level.
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
logging.getLogger('google.cloud.pubsub_v1.subscriber').setLevel(logging.WARNING)


def create_views(bigquery_util: bigquery_utils.CloudBigQueryUtils,
                 config: config_utils.Config,
                 target: config_utils.ConfigTarget):
  if not target.name:
    raise ValueError("Target has no name")
  sql_files = ['create-filtered-products.sql', 'create-ads-preview.sql']
  SEARCH_CONDITIONS = "SEARCH_CONDITIONS"
  condition = ''
  if target.merchant_id:
    if isinstance(target.merchant_id, list):
      condition = f' AND merchant_id IN {tuple(target.merchant_id)} '
    elif isinstance(target.merchant_id, str) and ',' in target.merchant_id:
      condition = f' AND merchant_id IN {tuple(target.merchant_id.split(", "))} '
    else:
      condition = f' AND merchant_id = {target.merchant_id} '
  # TODO: probably the condition isn't correct (it's too specific)
  if target.country_code:
    condition += f' AND destinations[SAFE_OFFSET(0)].approved_countries[SAFE_OFFSET(0)] = \'{target.country_code}\' '
  params = {SEARCH_CONDITIONS: condition}
  params['merchant_id'] = config.merchant_id
  params['target'] = target.name
  bigquery_util.execute_scripts(sql_files, config.dataset_id, params)


def set_permission_on_drive(fileId, email, credentials):
  driveAPI = discovery.build('drive', 'v3', credentials=credentials)
  logging.info(f'Adding write permissions to {email} on {fileId}')
  try:
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
  except HttpError as e:
    # NOTE: if the user doesn't exist then we'll get 500 "Internal Error"
    if e.status_code == 500:
      raise Exception(
          f'Error occured on adding drive permissions, please make sure that account \'{email}\' really exists ({e.reason})'
      ) from e
    raise Exception(f'Error occured on adding drive permissions: {e}') from e


def get_service_account_email(project_id: str):
  return f"{project_id}@appspot.gserviceaccount.com"


def create_spreadsheets(config: config_utils.Config,
                        target: config_utils.ConfigTarget,
                        credentials: credentials.Credentials,
                        share_with: str) -> bool:
  created = False
  merchant_id = target.merchant_id or config.merchant_id
  if not share_with:
    share_with = get_service_account_email(config.project_id)
  if target.page_feed_spreadsheetid:
    logging.info(
        'Skipped page feed spreadsheet creation as config contains a docid: ' +
        target.page_feed_spreadsheetid)
  else:
    logging.info('Creating a spreadsheet for page feed data')
    title = f"Product page feed (GMC {merchant_id} / GCP project {config.project_id})"
    target.page_feed_spreadsheetid = create_spreadsheet(title, credentials)
    created = True
  # set permission on the created spreadsheet for GAE default service account
  set_permission_on_drive(target.page_feed_spreadsheetid, share_with,
                          credentials)

  if target.adcustomizer_spreadsheetid:
    logging.info(
        'Skipped adcustomizer spreadsheet creation as config contains a docid: '
        + target.adcustomizer_spreadsheetid)
  else:
    logging.info('Creating a spreadsheet for ad customizer')
    title = f"Ad customizers feed (GMC {merchant_id} / GCP project {config.project_id})"
    target.adcustomizer_spreadsheetid = create_spreadsheet(title, credentials)
    created = True
  # set permission on the created spreadsheet for GAE default service account
  set_permission_on_drive(target.adcustomizer_spreadsheetid, share_with,
                          credentials)
  return created


def create_spreadsheet(title: str, credentials: credentials.Credentials) -> str:
  """Create a Google Spreadsheet (either for page feed or adcustomizers data)"""
  sheetsAPI = discovery.build('sheets', 'v4', credentials=credentials)
  result = sheetsAPI.spreadsheets().create(body={
      "sheets": [{
          "properties": {
              "title": "Main"
          }
      }],
      "properties": {
          "title": title
      }
  }).execute()
  spreadsheet_id = result['spreadsheetId']
  logging.info('Created spreadsheet: ' + spreadsheet_id)

  return spreadsheet_id


def backup_config(config_file_name: str, config: config_utils.Config,
                  credentials):
  """Backs up config file onto GCS (bucket "{project_id}-pdsa", will be created if doesn't exist)"""
  if not config_file_name.startswith('gs://') and config.project_id:
    gcs_path = config.project_id + '-pdsa'
    gcs_path = file_utils.upload_file_to_gcs(
        config_file_name, gcs_path,
        storage.Client(project=config.project_id, credentials=credentials))
    logging.info(
        f'config file ({config_file_name}) has been copied to {gcs_path}')


def enable_apis(apis: List[str], config: config_utils.Config, credentials):
  """Enables multiple Cloud APIs for a GCP project.

  Args:
    apis: The list of APIs to be enabled.

  Raises:
      Error: If the request was not processed successfully.
  """
  parent = f'projects/{config.project_id}'
  request_body = {'serviceIds': apis}
  client = discovery.build('serviceusage',
                           'v1',
                           credentials=credentials,
                           cache_discovery=False)
  operation = client.services().batchEnable(parent=parent,
                                            body=request_body).execute()
  cloud_utils.wait_for_operation(client.operations(), operation)


def create_pubsub_topic(config: config_utils.Config, credentials):
  """Creates a pub/sub topic for data transfer signal completion to"""
  topic_name = f'projects/{config.project_id}/topics/{config.pubsub_topic_dt_finish}'
  publisher = pubsub_v1.PublisherClient(credentials=credentials)

  # creating a topic with exising name will cause 409 Resource already exists in the project error,
  # so check first
  try:
    topic = publisher.get_topic(topic=topic_name)
    not_found = False
  except exceptions.NotFound:
    not_found = True
  if not_found:
    publisher.create_topic(name=topic_name)
  return topic_name


def wait_for_transfer_completion(
    pubsub_topic: str, config: config_utils.Config, credentials,
    data_transfer: cloud_data_transfer.CloudDataTransferUtils,
    transfer_config: TransferConfig):
  """Checks data transfer completed via creating an async pull subscription pub/sub completion topic"""

  def callback(message):
    message.ack()
    #print(message.data.decode())
    future.cancel()

  subscription_name = f'projects/{config.project_id}/subscriptions/install_script'
  with pubsub_v1.SubscriberClient(credentials=credentials) as subscriber:
    try:
      subscriber.delete_subscription(subscription=subscription_name)
    except exceptions.NotFound:
      pass  # expected
    subscriber.create_subscription(name=subscription_name, topic=pubsub_topic)
    future = subscriber.subscribe(subscription_name, callback)
    # if DT fails then waiting for a pub/sub will last forever, so first we'll wait the DT actually started
    # and only after that wait for a pub/sub
    data_transfer.wait_for_transfer_started(transfer_config)
    try:
      # NOTE: the next line blocks current thread in waiting and
      # only in callback on a message it'll be unblocked (future.cancel)
      future.result()
    except KeyboardInterrupt:
      future.cancel()
    subscriber.delete_subscription(subscription=subscription_name)


def create_subscription_to_update_feeds(pubsub_topic: str,
                                        config: config_utils.Config,
                                        credentials):
  """Creates a pub/sub push subscription to data transfer completion topic
     with signaling to GAE application to update page feed and adcustomizer feed"""
  subscription_name = f'projects/{config.project_id}/subscriptions/update_feeds'
  with pubsub_v1.SubscriberClient(credentials=credentials) as subscriber:
    try:
      subscriber.delete_subscription(subscription=subscription_name)
    except exceptions.NotFound:
      pass  # it's ok, subscription didn't exist

    # TODO: by default pubsub creates a subscription with expriration of 31 days of inactivity,
    # in UI it can be set as 'never exprire' but how to do it via API?

    # fetch GAE app hostname (it can be different depending on the chosen region)
    service = discovery.build("appengine", "v1", credentials=credentials)
    gae_info = service.apps().get(appsId=config.project_id).execute()
    if gae_info.get('iap', None) is None:
      raise Exception(
          f'IAP was not created for your App Engine application, please enable IAP in Cloud Console or run install.sh'
      )
    if not gae_info['iap'].get('enabled', False):
      raise Exception(
          f'Your App Engine application has disabled IAP, please enable it on https://console.cloud.google.com/security/iap'
      )
    hostname = gae_info['defaultHostname']
    oauth2ClientId = gae_info['iap']['oauth2ClientId']
    serviceAccount = gae_info['serviceAccount']
    gae_service = os.getenv('GAE_SERVICE')  # NOTE: the envvar will be define inside GAE
    if gae_service and gae_service.lower() != 'default':
      hostname = f'{gae_service.lower()}-dot-{hostname}'
    # TODO: there could be several application instances in a GCP project, each one in its own GAE service
    # we'll need to distintuish them somehow. Ideally we need to detect a current service when running in GAE
    subscriber.create_subscription(
        name=subscription_name,
        topic=pubsub_topic,
        push_config=pubsub_v1.types.PushConfig(
            push_endpoint=f'https://{hostname}/api/update',
            oidc_token=pubsub_v1.types.PushConfig.OidcToken(
                service_account_email=serviceAccount,
                audience=oauth2ClientId
            )))


@dataclass
class DeployOptions:
  skip_dt_run: bool
  user_email: str
  skip_spreadsheets: bool


def deploy(config: config_utils.Config, credentials: credentials.Credentials,
           options: DeployOptions) -> bool:
  """Deploys cloud components.
    Return: bool - whether config was updated (true)
  """
  errors = config.validate()
  if len(errors):
    raise ValueError(f'Configuration is invalid: {errors}')

  logging.info('Enabling apis')
  enable_apis([
      'bigquery.googleapis.com', 'bigquerydatatransfer.googleapis.com',
      'sheets.googleapis.com', 'drive.googleapis.com', 'pubsub.googleapis.com',
      'iap.googleapis.com', 'cloudresourcemanager.googleapis.com'
  ], config, credentials)
  logging.info('apis have been enabled')

  logging.info('Creating %s dataset.', config.dataset_id)
  bigquery_client = bigquery_utils.CloudBigQueryUtils(config.project_id,
                                                      credentials,
                                                      config.dataset_location)
  bigquery_client.create_dataset_if_not_exists(config.dataset_id,
                                               config.dataset_location)

  data_transfer = cloud_data_transfer.CloudDataTransferUtils(
      config.project_id, config.dataset_location, credentials)
  pubsub_topic = create_pubsub_topic(config, credentials)
  # create or reuse data transfer for GMC
  transfer_config = data_transfer.create_merchant_center_transfer(
      config.merchant_id, config.dataset_id, config.dt_schedule, pubsub_topic,
      options.skip_dt_run)
  # TODO: it's very common for new transfers to fail with: "No Products data to transfer found for your Google Merchant Center account. If you have just created this transfer, you may need to wait for up to a day before the data of your Google Merchant Center account are prepared and available for the transfer."

  if not options.skip_dt_run:
    logging.info('Waiting for Data Transfer to complete...')
    wait_for_transfer_completion(pubsub_topic, config, credentials,
                                 data_transfer, transfer_config)
    logging.info('Data Transfer has completed')

  # ads_config = data_transfer.create_google_ads_transfer(ads_customer_id, args.dataset_id)

  if not config.targets:
    logging.warning('No targets found in configuration, exiting')
    exit()

  created = False
  for target in config.targets:
    logging.info(
        f'Creating solution specific views for \'{target.name}\' target.')
    create_views(bigquery_client, config, target)

    # creating spreadsheets for page feed data and adcustomizers
    if not options.skip_spreadsheets:
      created = created or create_spreadsheets(config, target, credentials,
                                               options.user_email)

  create_subscription_to_update_feeds(pubsub_topic, config, credentials)
  logging.info(
      'Created pub/sub subscription for data transfer to call GAE app for updating feeds'
  )

  logging.info('Installation is complete!')
  return created


def add_args(parser: argparse.ArgumentParser):
  parser.add_argument('--skip-dt-run',
                      dest='skip_dt_run',
                      action="store_true",
                      help='Suppress running data transfer if it exists')
  parser.add_argument('--user-email',
                      dest='user_email',
                      help='User email to share created spreadsheets with')
  parser.add_argument('--skip-spreadsheets',
                      dest='skip_spreadsheets',
                      action='store_true')
  parser.add_argument('--create-spreadsheets',
                      dest='create_spreadsheets',
                      action='store_true')


def main():
  args = config_utils.parse_arguments(only_known=False, func=add_args)
  config = config_utils.get_config(args)
  pprint(vars(config))
  credentials = auth.get_credentials(args)

  if args.service_account_file and getattr(credentials, "project_id",
                                           None) != config.project_id:
    logging.error(
        f'Provided service account belongs to a different project ({getattr(credentials, "project_id", None)}) '
        f'than your current project in config ({config.project_id})')
    exit()
  if args.service_account_file and not args.user_email:
    logging.error(f'You supplied a service account but not a user email')
    exit()

  if args.create_spreadsheets:
    for target in config.targets:
      create_spreadsheets(config, target, credentials, args.user_email)
    return

  created = deploy(
      config, credentials,
      DeployOptions(args.skip_dt_run, args.user_email, args.skip_spreadsheets))

  config_file_path = args.config or 'config.json'
  if created:
    # overwrite config file with new data
    config_utils.save_config(config, config_file_path)

  # As we could have modified the config (e.g. put a spreadsheet id),
  # we need to save it to a well-known location - GCS bucket {project_id}-pdsa:
  backup_config(config_file_path, config, credentials)


if __name__ == '__main__':
  main()
