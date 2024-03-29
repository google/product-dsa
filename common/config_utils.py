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
import argparse
from typing import Callable, List, Tuple
from common import auth, file_utils
import os
import json
from enum import Enum
import re


class ConfigItemBase(object):

  def __init__(self):
    # copy class atrributes (with values) into the instance
    members = [
        attr for attr in dir(self)
        if not attr.startswith("__") and attr != 'update' and attr != 'validate'
    ]
    for attr in members:
      setattr(self, attr, getattr(self, attr))

  def update(self, kw):
    """Update current object with values from json/dict.
       Only know properties (i.e. those that exist in object's class as class attributes) are set
    """
    cls = type(self)
    for k in kw:
      if hasattr(cls, k):
        new_val = kw[k]
        def_val = getattr(cls, k)
        if (new_val == "" and def_val != ""):
          new_val = def_val
        setattr(self, k, new_val)


class ConfigTarget(ConfigItemBase):
  # target name (required)
  name: str = ''
  # a child GMC account (if differs from the GMC account specified in source) (optional)
  merchant_id: str = ''
  # Google Ads customer id (not used currently)
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
  # template for ad descriptions, if empty product descriptions from GMC will be used,
  # otherwise can be a template containing product fields in curly braces, e.g. "{title} ({price_value})"
  ad_description_template: str = ''
  # category descriptions, should be filled for category-based campaign labels
  category_ad_descriptions: dict = {}
  max_image_dimension: int = 1200
  """Maximum dimension for images (either width or height), 0 - no limit"""
  skip_additional_images: bool = False
  """Do not download additional product images (for image extensions in campaign data)"""
  max_image_count: int or None = None
  """Limit total amount of product images"""
  country_code: str = ''
  """Country code for selecting one product of many for several countries. Optional, but mandatory if products in GMC duplicated with different approved_countries"""
  product_description: str = ''
  """Static description for all product-level ads. Still can be combined with adcustomizers"""
  product_description_as_fallback_only: bool = False
  """Use static description (product_description) only if product description exceeds maximum ad description length"""
  image_filter: str = ''
  image_filter_re: List[Tuple[bool, re.Pattern]] = []
  """Additional condition to filter products from GMC (as SQL expression)"""
  gmc_sql_condition: str = ''

  def validate(self, generation=False) -> List:
    errors = []
    if not self.name or re.match('[^A-Za-z0-9_\-]', self.name):
      errors.append({
          'field':
              'name',
          'error':
              'Target name should not contain spaces (only symbols A-Za-z,0-9,_,-)'
      })
    if generation:
      if not self.page_feed_spreadsheetid:
        errors.append({
            'field': 'page_feed_spreadsheetid',
            'error': 'No spreadsheet id for page feed found in configuration'
        })
      if not self.dsa_website:
        errors.append({
            'field': 'dsa_website',
            'error': 'No DSA website found in configuration'
        })
      if not self.max_image_dimension is None:
        correct = False
        try:
          correct = int(self.max_image_dimension) >= 0
        except:
          correct = False
        if not correct:
          errors.append({
            'field':
                'max_image_dimension',
            'error':
                'max_image_dimension should either empty or a non negative integer'
          })
    return errors

  def init_image_filter(self):
    if self.image_filter:
      for expr in self.image_filter.split(';'):
        expr = expr.strip()
        if not expr:
          continue
        # Commenting this out because we'll only support excluding images for now
        # because it's confusing how different filters will apply together
        # negative = expr.startswith('!')
        # if negative:
        #   expr = expr[1:]
        pattern = re.compile(
            expr.replace('.', '\.').replace('*', '.*').replace('?',
              '.?').replace('(', '\(').replace(')', '\)'))
        negative = True
        self.image_filter_re.append((negative ,pattern))


class Config(ConfigItemBase):
  # GCP project id
  project_id: str = ''
  # dataset id in BigQuery for GMC-BQ data transfer
  dataset_id: str = 'gmcdsa'
  # location for dataset in BigQuery (all locations are in Europe by default, see install-web.sh as well)
  dataset_location: str = 'europe'
  # GMC merchant id
  merchant_id: int = 0
  # DataTransfer schedule (syntax - https://cloud.google.com/appengine/docs/flexible/python/scheduling-jobs-with-cron-yaml#cron_yaml_The_schedule_format)
  # if empty default scheduling will be used - run DT daily. E.g. 'every 6 hours'
  dt_schedule: str = ''
  # pub/sub topic id for publishing message on GMC Data Transfer completions
  pubsub_topic_dt_finish: str = 'gmc-dt-finish'

  def __init__(self):
    super().__init__()
    self.targets: List[ConfigTarget] = []
    self.errors = []

  def validate(self, generation=False, validate_targets=True) -> List:
    errors = []
    if not self.project_id:
      errors.append({
          'field':
              'project_id',
          'error':
              'No project_id found in configuration and it couldn\'t be detected'
      })
    if not self.merchant_id:
      errors.append({
          'field': 'merchant_id',
          'error': 'No merchant_id found in configuration'
      })
    if not self.dataset_id:
      errors.append({
          'field': 'dataset_id',
          'error': 'No dataset_id found in configuration'
      })
    if not self.pubsub_topic_dt_finish:
      errors.append({
          'field': 'pubsub_topic_dt_finish',
          'error': 'No pub/sub topic id specified'
      })
    if validate_targets and len(self.targets):
      for target in self.targets:
        for error in target.validate(generation):
          error['field'] = f'targets.{target.name}.' + error['field']
          errors.append(error)
      #nested_errors = [t.validate() for t in self.targets]
      #errors.extend(itertools.chain(*nested_errors))
    self.errors = errors

    return errors

  def to_dict(self, include_defaults=True) -> dict:
    values = {
        "project_id": self.project_id,
        "dataset_id": self.dataset_id,
        "dataset_location": self.dataset_location,
        "merchant_id": self.merchant_id,
        "dt_schedule": self.dt_schedule,
        "pubsub_topic_dt_finish": self.pubsub_topic_dt_finish,
        "targets": []
    }
    for t in self.targets:
      target_json = {
          "name": t.name,
          "merchant_id": t.merchant_id,
          "ads_customer_id": t.ads_customer_id,
          "country_code": t.country_code,
          "product_campaign_name": t.product_campaign_name,
          "category_campaign_name": t.category_campaign_name,
          "dsa_website": t.dsa_website,
          "dsa_lang": t.dsa_lang,
          "page_feed_name": t.page_feed_name,
          "page_feed_spreadsheetid": t.page_feed_spreadsheetid,
          "adcustomizer_feed_name": t.adcustomizer_feed_name,
          "adcustomizer_spreadsheetid": t.adcustomizer_spreadsheetid,
          "page_feed_output_file": t.page_feed_output_file,
          "campaign_output_file": t.campaign_output_file,
          "adcustomizer_output_file": t.adcustomizer_output_file,
          "ad_description_template": t.ad_description_template,
          "category_ad_descriptions": t.category_ad_descriptions,
          "max_image_dimension": t.max_image_dimension,
          "skip_additional_images": t.skip_additional_images,
          "max_image_count": t.max_image_count,
          "product_description": t.product_description,
          "product_description_as_fallback_only": t.product_description_as_fallback_only,
          "image_filter": t.image_filter,
          "gmc_sql_condition": t.gmc_sql_condition
      }
      values["targets"].append(target_json)
    return values


class ApplicationErrorReason(Enum):
  INVALID_DEPLOYMENT = "invalid_deployment"
  NOT_INITIALIZED = "not_initialized"
  INVALID_CLOUD_SETUP = "invalid_cloud_setup"
  """Cloud component(s) either was not created or in failed state"""
  INVALID_CONFIG = "invalid_config"
  """Missing or incorrect values in configuraiton file"""
  INVALID_DATA = "invalid_data"


class ApplicationError:

  def __init__(self, reason: ApplicationErrorReason, description: str):
    self.reason = reason
    self.description = description

  def to_dict(self):
    return {"reason": self.reason.value, "description": self.description}


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
  parser.add_argument('--project_id', '--project-id', help='GCP project id.')

  auth.add_auth_arguments(parser)
  if func:
    func(parser)
  if only_known:
    args = parser.parse_known_args()[0]
  else:
    args = parser.parse_args()
  args.config = args.config or os.environ.get('CONFIG') or 'config.json'
  return args


def get_config_url(args: argparse.Namespace):
  config_file_name = args.config or os.environ.get('CONFIG') or 'config.json'
  if config_file_name.find('$PROJECT_ID') > -1:
    project_id = find_project_id(args)
    if project_id is None:
      raise Exception(
          'Config file url contains macro $PROJECT_ID but project id isn\'t specified and can\'t be detected from environment'
      )
    config_file_name = config_file_name.replace('$PROJECT_ID', project_id)
  return config_file_name


def get_config(args: argparse.Namespace) -> Config:
  """ Read config file and merge settings from it, command line args and env vars."""
  config_file_name = get_config_url(args)
  content = file_utils.get_file_content(config_file_name)
  cfg_dict: dict = json.loads(content)
  config = Config()
  config.update(cfg_dict)
  if cfg_dict.get('targets'):
    for target_dict in cfg_dict['targets']:
      target = ConfigTarget()
      target.update(target_dict)
      config.targets.append(target)
      # some normalization
      if target.ads_customer_id:
        target.ads_customer_id = target.ads_customer_id.replace('-', '')

  if len(config.targets) == 1 and not config.targets[0].name:
    config.targets[0].name = "default"

  # project id
  if getattr(args, "project_id", ''):
    config.project_id = getattr(args, "project_id")
  if not config.project_id:
    config.project_id = find_project_id(args)

  return config


def find_project_id(args: argparse.Namespace):
  if getattr(args, "project_id", ''):
    project_id = getattr(args, "project_id")
  project_id = os.getenv('GCP_PROJECT') or \
               os.getenv('GOOGLE_CLOUD_PROJECT') or \
               os.getenv('DEVSHELL_PROJECT_ID')
  # if service account key file specified via CLI, extract project_id from it
  if not project_id and getattr(args, "service_account_file", ''):
    # detect project id from service account key file
    with open(args.service_account_file) as f:
      credentials = json.load(f)
    project_id = credentials['project_id']
  # else if this is running locally then GOOGLE_APPLICATION_CREDENTIALS can be defined
  if not project_id and 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    with open(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), 'r') as fp:
      credentials = json.load(fp)
    project_id = credentials['project_id']

  return project_id


def save_config(config: Config, filename: str):
  config_file_name = filename or 'config.json'
  #yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None
  #content = yaml.dump(config)
  content = json.dumps(config.to_dict())
  #default=lambda x: x.__dict__
  file_utils.save_file_content(config_file_name, content)
