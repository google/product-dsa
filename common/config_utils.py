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
import argparse
from typing import Callable
from google.oauth2 import service_account
import os
import yaml
import json
from common import auth, file_utils


class Config(object):
  # GCP project id
  project_id: str = ''
  # location for dataset in BigQuery
  dataset_location: str = 'us'
  # dataset id in BigQuery for GMC-BQ data transfer
  dataset_id: str = 'gmcdsa'
  # GMC merchant id
  merchant_id: int = 0
  # Google Ads customer id
  ads_customer_id: str = ''
  # campaign name for product-level
  product_campaign_name: str = ''
  # campaign name for category-level
  category_campaign_name: str = ''
  # DSA website
  dsa_website: str = ''
  # DSA language (en)
  dsa_lang: str = 'en'
  # name of page feed (by default 'pdsa-page-feed')
  page_feed_name: str = 'pdsa-page-feed'
  # spreadsheet id for DSA page feed (should be generated during setup)
  page_feed_spreadsheetid: str = ''
  # name of adcustomizer feed (by default 'pdsa-adcustomizers')
  adcustomizer_feed_name: str = 'pdsa-adcustomizers'
  # spreadsheet id for adcustomizers feed (should be generated during setup)
  adcustomizer_spreadsheetid: str = ''
  # file name for output csv file with page feed
  page_feed_output_file: str = 'page-feed.csv'
  # file name for output csv file with campaign data for Ads Editor
  campaign_output_file: str = 'gae-campaigns.csv'
  # file name for output csv file with ad-customizer data
  adcustomizer_output_file: str = 'ad-customizer.csv'
  # folder for downloading images from GMC, if relative and output_folder specified then they will be joined
  image_folder: str = 'images'
  # output folder path, will be common base path for all outputs
  output_folder: str = ''
  # pub/sub topic id for publishing message on GMC Data Transfer completions
  pubsub_topic_dt_finish: str = 'gmc-dt-finish'
  # template for ad descriptions, if empty product descriptions from GMC will be used,
  # otherwise can be a template containing product fields in curly braces, e.g. "{title} ({price_value})"
  ad_description_template: str = ''
  # category descriptions, should be filled for category-based campaign labels
  category_ad_descriptions: dict = {}
  # DataTransfer schedule (syntax - https://cloud.google.com/appengine/docs/flexible/python/scheduling-jobs-with-cron-yaml#cron_yaml_The_schedule_format)
  # if empty default scheduling will be used - run DT daily. E.g. 'every 6 hours'
  dt_schedule: str = ''

  def __init__(self):
    # copy class atrributes (with values) into the instance
    members = [
        attr
        for attr in dir(self)
        if not attr.startswith("__") and attr != 'update'
    ]
    for attr in members:
      setattr(self, attr, getattr(self, attr))

  def update(self, kw):
    for k in kw:
      setattr(self, k, kw[k])


def parse_arguments(
    only_known: bool = False,
    func: Callable[[argparse.ArgumentParser],
                   None] = None) -> argparse.Namespace:
  """Initialize command line parser using argparse.

  Returns:
    An argparse.ArgumentParser.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument('--config', help='Config file name')
  parser.add_argument('--project_id', help='GCP project id.')
  parser.add_argument('--merchant_id',
                      help='Google Merchant Center Account Id.')
  parser.add_argument('--dataset_id', help='BigQuery dataset id.')
  parser.add_argument(
      '--dataset_location',
      help=
      'BigQuery dataset and BigQuery Data Transfer location (by default: US).')
  parser.add_argument('--ads_customer_id',
                      help='Google Ads External Customer Id.')

  auth.add_auth_arguments(parser)
  if func:
    func(parser)
  if only_known:
    args = parser.parse_known_args()[0]
  else:
    args = parser.parse_args()
  args.config = args.config or os.environ.get('CONFIG') or 'config.yaml'
  return args


def get_config_url(args: argparse.Namespace):
  config_file_name = args.config or os.environ.get('CONFIG') or 'config.yaml'
  if config_file_name.find('$PROJECT_ID') > -1:
    project_id = args.project_id or _find_project_id()
    if project_id is None:
      raise Exception(
          'Config file url contains macro $PROJECT_ID but project id isn\'t specified and can\'t be detected from environment'
      )
    config_file_name = config_file_name.replace(
        '$PROJECT_ID', args.project_id or _find_project_id())
  return config_file_name


def get_config(args: argparse.Namespace) -> Config:
  """ Read config file and merge settings from it, command line args and env vars."""
  config_file_name = get_config_url(args)
  content = file_utils.get_file_content(config_file_name)
  cfg_dict = yaml.load(content, Loader=yaml.SafeLoader)
  config = Config()
  config.update(cfg_dict)
  # project id
  if args.project_id:
    config.project_id = args.project_id

  # dataset id
  config.dataset_id = args.dataset_id or os.environ.get(
      'DATASET_ID') or config.dataset_id
  # dataset location
  config.dataset_location = args.dataset_location or os.environ.get(
      'DATASET_LOCATION') or config.dataset_location
  # merchant id
  config.merchant_id = args.merchant_id or os.environ.get(
      'MERCHANT_ID') or config.merchant_id
  # ads customer id
  config.ads_customer_id = args.ads_customer_id or os.environ.get(
      'ADS_CUSTOMER_ID') or config.ads_customer_id
  if config.ads_customer_id:
    config.ads_customer_id = config.ads_customer_id.replace('-', '')

  validate_project_id(config, args)
  return config


def validate_project_id(config: Config, args = None):
  project_id = config.project_id
  if project_id:
    return
  project_id = _find_project_id()
  if not project_id and args.service_account_file:
    # detect project id from service account key file
    credentials = service_account.Credentials.from_service_account_file(args.service_account_file)
    project_id = credentials.project_id
  if not project_id:
    raise Exception('Failed to determine project_id')
  config.project_id = project_id


def _find_project_id():
  project_id = os.getenv('GCP_PROJECT') or \
               os.getenv('GOOGLE_CLOUD_PROJECT') or \
               os.getenv('DEVSHELL_PROJECT_ID')
  # else if this is running locally then GOOGLE_APPLICATION_CREDENTIALS should be defined
  if not project_id and 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    with open(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), 'r') as fp:
      credentials = json.load(fp)
    project_id = credentials['project_id']
  return project_id


def save_config(config: Config, filename: str):
  config_file_name = filename or 'config.yaml'
  yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None
  content = yaml.dump(config)
  file_utils.save_file_content(config_file_name, content)
