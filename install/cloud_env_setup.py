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

import argparse
from io import TextIOWrapper
import logging
import os
from typing import NamedTuple, Dict, Union
import google.auth
from google.oauth2 import service_account  # type: ignore
from google_auth_oauthlib import flow
from google.auth import credentials
from google.cloud import bigquery
import yaml
from pprint import pprint

import cloud_bigquery
import cloud_data_transfer


# Set logging level.
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)

_SCOPES = ['https://www.googleapis.com/auth/cloud-platform',
           'https://www.googleapis.com/auth/bigquery']

# BigQuery dataset name to use by default
_DATASET_ID = 'gmcdsa'
# Location for BigQuery dataset and BQ data transfers to use by default
_DATASET_LOCATION = 'us'

class Config(object):
  project_id: str = ''
  dataset_location: str = ''
  dataset_id: str = ''
  merchant_id: int = 0
  ads_customer_id: str = ''

  def update(self, kw):
    for k in kw:
      setattr(self, k, kw[k])


def parse_arguments() -> argparse.Namespace:
  """Initialize command line parser using argparse.

  Returns:
    An argparse.ArgumentParser.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument('--config', help='Config file name')
  parser.add_argument('--project_id', help='GCP project id.')
  parser.add_argument('--merchant_id', help='Google Merchant Center Account Id.')
  parser.add_argument('--dataset_id', help='BigQuery dataset id.')
  parser.add_argument('--dataset_location', help='BigQuery dataset and BigQuery Data Transfer location (by default: US).')

  parser.add_argument('--client-secrets-file', dest='client_secrets_file',
                      help='Path to user secrets file with oauth credentials (authenticating as a user).')
  parser.add_argument('--service-account-key-file', dest='service_account_file',
                      help='Path to service account key file (authenticating as a service account).')
  parser.add_argument('--non-interactive', dest='non_interactive',
                      help='Specify if using client-secrets-file option and running via ssh.')
  parser.add_argument('--ads_customer_id', help='Google Ads External Customer Id.')

  return parser.parse_args()


def open_relative_file(file_name: str) -> TextIOWrapper:
  """Opens a file for reading relatively to the current module."""
  working_directory = os.path.dirname(__file__)
  return open(os.path.join(working_directory, file_name), "rb")


def get_credentials(args: argparse.Namespace) -> credentials.Credentials:
  if args.client_secrets_file:
    try:
      appflow = flow.InstalledAppFlow.from_client_secrets_file(
          args.client_secrets_file, scopes=_SCOPES)
      if args.non_interactive:
        appflow.run_console()
      else:
        appflow.run_local_server()
      credentials = appflow.credentials
    except ValueError as e:
      raise Exception(
          "Invalid json file for web app authenication") from e
  elif args.service_account_file:
    try:
      credentials = service_account.Credentials.from_service_account_file(
          args.service_account_file, _SCOPES)
    except ValueError as e:
      raise Exception(
          "Invalid json file for service account authenication") from e
  else:
    credentials = google.auth.default()

  return credentials


def get_config(args: argparse.Namespace) -> Config:
  config_file_name = args.config or 'config.yaml'
  """ Read config.yml file and return Config object."""
  with open_relative_file(config_file_name) as config_file:
    cfg_dict = yaml.load(config_file, Loader=yaml.SafeLoader)
    config = Config()
    config.update(cfg_dict)
    if (args.project_id):
      config.project_id = args.project_id
    if (args.dataset_id):
      config.dataset_id = args.dataset_id
    elif (not config.dataset_id):
      config.dataset_id = _DATASET_ID
    if (args.dataset_location):
      config.dataset_location = args.dataset_location
    elif (not config.dataset_location):
      config.dataset_location = _DATASET_LOCATION
    if (args.merchant_id):
      config.merchant_id = args.merchant_id
    if (args.ads_customer_id):
      config.ads_customer_id = args.ads_customer_id

    return config


def main():
  args = parse_arguments()

  config = get_config(args)
  pprint(vars(config))
  credentials = get_credentials(args)

  logging.info('Creating %s dataset.', config.dataset_id)
  bigquery_util = cloud_bigquery.CloudBigQueryUtils(config.project_id, credentials)
  bigquery_util.create_dataset_if_not_exists(config.dataset_id, config.dataset_location)

  data_transfer = cloud_data_transfer.CloudDataTransferUtils(config.project_id,
      config.dataset_location, credentials)
  merchant_center_config = data_transfer.create_merchant_center_transfer(
      config.merchant_id, config.dataset_id)

  ads_customer_id = config.ads_customer_id.replace('-', '')
  # ads_config = data_transfer.create_google_ads_transfer(ads_customer_id,
  #                                                       args.dataset_id)
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

  logging.info('Creating solution specific views.')
  # Sql files to be executed in a specific order. The prefix "scripts" should be omitted.
  sql_files = [
     'product_filter.sql',
  ]
  bigquery_util.execute_queries(sql_files, config.dataset_id, config.dataset_location,
    config.merchant_id, ads_customer_id)

  logging.info('Curating PageFeeds URLs')
  query_params = {
      'project_id': config.project_id,
      'dataset': config.dataset_id,
      'merchant_id': config.merchant_id
  }
  query = bigquery_util.get_main_workflow_sql( config.dataset_id,
    config.merchant_id, config.ads_customer_id)
  data_transfer.schedule_query(f'Product DSA workflow - {config.dataset_id} - {config.merchant_id}',
                               query)
  logging.info('Job created to run Product DSA main workflow.')

  logging.info('installation is complete!')


if __name__ == '__main__':
  main()

