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
from common import auth, file_utils
import os
import yaml
import json

# BigQuery dataset name to use by default
_DATASET_ID = 'gmcdsa'
# Location for BigQuery dataset and BQ data transfers to use by default
_DATASET_LOCATION = 'us'
# Location for Cloud Scheduler
_SCHEDULER_LOCATION = 'europe-west1'


class Config(object):
  project_id: str = ''
  dataset_location: str = ''
  dataset_id: str = ''
  merchant_id: int = 0
  ads_customer_id: str = ''
  product_campaign_name: str = ''
  category_campaign_name: str = ''
  dsa_website: str = ''
  dsa_lang: str = ''
  page_feed_name: str = ''
  page_feed_spreadsheetid: str = ''
  page_feed_output_file: str = ''
  campaign_output_file: str = ''
  scheduler_location: str = ''

  def update(self, kw):
    for k in kw:
      setattr(self, k, kw[k])


def parse_arguments(only_known: bool = False) -> argparse.Namespace:
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
  parser.add_argument('--scheduler_location', help='Cloud Scheduler location id (by default: europe-west1)')
  parser.add_argument('--ads_customer_id',
                      help='Google Ads External Customer Id.')

  auth.add_auth_arguments(parser)
  if only_known:
    args = parser.parse_known_args()[0]
  else:
    args = parser.parse_args()
  args.config = args.config or os.environ.get('CONFIG') or 'config.yaml'
  return args

def get_config(args: argparse.Namespace) -> Config:
  config_file_name = args.config or os.environ.get('CONFIG') or 'config.yaml'
  """ Read config.yml file and return Config object."""
  content = file_utils.get_file_content(config_file_name)
  cfg_dict = yaml.load(content, Loader=yaml.SafeLoader)
  config = Config()
  config.update(cfg_dict)
  # project id
  if args.project_id:
    config.project_id = args.project_id

  # dataset id
  if args.dataset_id:
    config.dataset_id = args.dataset_id
  elif not config.dataset_id:
    config.dataset_id = os.environ.get('DATASET_ID') or _DATASET_ID
  # dataset location
  if args.dataset_location:
    config.dataset_location = args.dataset_location
  elif not config.dataset_location:
    config.dataset_location = os.environ.get(
        'DATASET_LOCATION') or _DATASET_LOCATION
  # merchant id
  if args.merchant_id:
    config.merchant_id = args.merchant_id
  elif not config.merchant_id:
    config.merchant_id = os.environ.get('MERCHANT_ID')
  # ads customer id
  if args.ads_customer_id:
    config.ads_customer_id = args.ads_customer_id
  elif not config.ads_customer_id:
    config.ads_customer_id = os.environ.get('ADS_CUSTOMER_ID')
  if config.ads_customer_id:
    config.ads_customer_id = config.ads_customer_id.replace('-', '')
  # scheduler location
  if args.scheduler_location:
    config.scheduler_location = args.scheduler_location
  elif not config.scheduler_location:
    config.scheduler_location = os.getenv(
        'SCHEDULER_LOCATION') or _SCHEDULER_LOCATION

  validate_project_id(config)
  return config


def validate_project_id(config: Config):
  project_id = config.project_id
  if project_id:
    return
  project_id = os.environ['GCP_PROJECT'] or \
               os.environ['GOOGLE_CLOUD_PROJECT'] or \
               os.environ['DEVSHELL_PROJECT_ID']
  # else if this is running locally then GOOGLE_APPLICATION_CREDENTIALS should be defined
  if not project_id and 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as fp:
      credentials = json.load(fp)
    project_id = credentials['project_id']
  if not project_id:
    raise Exception('Failed to determine project_id')
  config.project_id = project_id


def save_config(config: Config, filename: str):
  config_file_name = filename or 'config.yaml'
  yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None
  content = yaml.dump(config)
  file_utils.save_file_content(config_file_name, content)
