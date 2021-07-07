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

import cloud_bigquery
import cloud_data_transfer


# Set logging level.
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)

_SCOPES = ['https://www.googleapis.com/auth/cloud-platform',
           'https://www.googleapis.com/auth/bigquery']

# BigQuery dataset name to use by default
_DATASET_ID = 'gmcdsa'


class Config(object):
  project_id: str
  dataset_location: str
  dataset_id: str
  merchant_id: int

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
  parser.add_argument('--dataset_id', help='BigQuery dataset id.', default=_DATASET_ID)
  parser.add_argument('--merchant_id', help='Google Merchant Center Account Id.')
  parser.add_argument('--client-secrets-file', dest='client_secrets_file',
                      help='Path to user secrets file with oauth credentials (authenticating as a user).')
  parser.add_argument('--service-account-key-file', dest='service_account_file',
                      help='Path to service account key file (authenticating as a service account).')
  parser.add_argument('--non-interactive', dest='non_interactive',
                      help='Specify if using client-secrets-file option and running via ssh.')
  # parser.add_argument(
  #     '--ads_customer_id',
  #     help='Google Ads External Customer Id.',
  #     required=True)

  return parser.parse_args()

def open_relative_file(file_name: str) -> TextIOWrapper:
  """Opens a file for reading relatively to the current module."""
  working_directory = os.path.dirname(__file__)
  return open(os.path.join(working_directory, file_name), "r")

def load_language_codes(project_id: str, dataset_id: str) -> None:
  """Loads language codes."""
  client = bigquery.Client(project=project_id)
  fully_qualified_table_id = f'{project_id}.{dataset_id}.language_codes'
  job_config = bigquery.LoadJobConfig(
      source_format=bigquery.SourceFormat.CSV,
      skip_leading_rows=1,
      autodetect=True,
  )
  file_name = 'data/language_codes.csv'
  with open_relative_file(file_name) as source_file:
    job = client.load_table_from_file(
        source_file, fully_qualified_table_id, job_config=job_config)

  job.result()


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
    if (args.merchant_id):
      config.merchant_id = args.merchant_id
    return config


def main():
  args = parse_arguments()

  config = get_config(args)
  credentials = get_credentials(args)
  #TODO: dump config to log logging

  logging.info('Creating %s dataset.', config.dataset_id)
  bigquery_util = cloud_bigquery.CloudBigQueryUtils(config.project_id, credentials)
  bigquery_util.create_dataset_if_not_exists(config.dataset_id, config.dataset_location)

  data_transfer = cloud_data_transfer.CloudDataTransferUtils(config.project_id,
      config.dataset_location, credentials)
  merchant_center_config = data_transfer.create_merchant_center_transfer(
      config.merchant_id, config.dataset_id)

  # ads_customer_id = args.ads_customer_id.replace('-', '')
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

  load_language_codes(args.project_id, args.dataset_id)

  # logging.info('Creating solution specific views.')
  # Sql files to be executed in a specific order. The prefix "scripts" should be omitted.
  # sql_files = [
  #    '1_product_view.sql',
  #    'targeted_products/targeted_product_ddl.sql',
  #    'targeted_products/construct_parsed_criteria.sql',
  #    '2_product_metrics_view.sql',
  #    '3_customer_view.sql',
  #    '4_product_detailed_view.sql',
  #    'materialize_product_detailed.sql',
  #    'materialize_product_historical.sql',
  # ]
  # cloud_bigquery.execute_queries(sql_files, args.project_id, args.dataset_id, args.merchant_id, ads_customer_id)

  # logging.info('Updating targeted products')
  # query_params = {
  #     'project_id': args.project_id,
  #     'dataset': args.dataset_id,
  #     'merchant_id': args.merchant_id,
  #     'external_customer_id': ads_customer_id
  # }
  # query = cloud_bigquery.get_main_workflow_sql(
  #   args.project_id, args.dataset_id, args.merchant_id, ads_customer_id)
  # data_transfer.schedule_query(f'Main workflow - {args.dataset_id} - {ads_customer_id}',
  #                              query)
  # logging.info('Job created to run markup main workflow.')

  logging.info('installation is complete!')


if __name__ == '__main__':
  main()
