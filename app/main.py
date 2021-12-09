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
import argparse
import logging
from typing import Dict, List
from datetime import datetime
import os
import csv
import resource
from google.auth import credentials
from pprint import pprint
from common import auth, config_utils, sheets_utils, file_utils, bigquery_utils
from app.context import Context, ContextOptions
from app import campaign_mgr

logging.basicConfig(format='[%(asctime)s][%(name)s] %(message)s',
                    level=logging.INFO,
                    datefmt='%H:%M:%S')
logging.getLogger('google.api_core').setLevel(logging.WARNING)


def execute_sql_query(script_name: str,
                      context: Context,
                      params: Dict[str, str] = None):
  if not context.target:
    raise ValueError(f'Context does not have a target')
  if not params:
    params = {}
  params['target'] = context.target.name
  return context.bq_client.execute_queries(script_name,
                                           context.config.dataset_id, params)


def validate_config(context: Context):

  def _validate_target(target: config_utils.ConfigTarget, errors: List):
    errors.extend(target.validate(generation=True))
    context.target = target
    params = {'WHERE_CLAUSE': "WHERE trim(lab) NOT LIKE 'product_%'"}
    category_labels = execute_sql_query('get-labels.sql', context, params)
    if category_labels.total_rows:
      missing_category_desc = False
      err_message = ''
      for row in category_labels:
        desc = None
        if target.category_ad_descriptions:
          desc = target.category_ad_descriptions.get(row[0])
        if not desc or desc == '':
          missing_category_desc = True
          err_message = f'Missing category description for label \'{row[0]}\'\n'
      if missing_category_desc:
        err_message = 'Update the missing categories in the config.json file:\n' + err_message
        errors.append({
            'field': 'category_ad_descriptions',
            'error': err_message
        })

  errors = []
  errors = context.config.validate(generation=True, validate_targets=False)
  if context.target:
    _validate_target(context.target, errors)
  else:
    # validate all targets
    for target in context.config.targets:
      _validate_target(target, errors)

  if errors:
    message = ''
    for err in errors:
      message += (err['field'] + ': ' + err['error'] + '\n')
    return {'valid': False, 'errors': errors, 'message': message}

  return {'valid': True, 'errors': []}


def create_or_update_page_feed(generate_csv: bool, context: Context):
  step_name = 'page feed ' + ('creation' if generate_csv else 'updating')
  ts_start = datetime.now()
  # Execute a SQL script (TODO: read its name from config) to get data for DSA page feed
  # The contract for the script:
  #   we expect 2-columns: 'Page_URL' and 'Custom_label'
  #   both columns should not be empty or NULL
  #   the Custom_label column can contain one or many label, separated by ';'
  #   values in Page_URL column should be unique
  # NOTE: currently we don't validate all those invariants, only assume they
  logging.info(f'Starting "{step_name}" step')
  data = execute_sql_query('create-page-feed.sql', context)
  logging.info(f'Page-feed query returned {data.total_rows} rows')

  values = []
  for row in data:
    # add a common label for all our URLs
    labels = row[1] + '; PDSA'
    # and add a common label for product-only URLs
    for label in labels.split(';'):
      label = label.strip()
      if label.startswith('product_'):
        labels += '; PDSA_PRODUCT'
        break

    values.append([row[0], labels])

  if generate_csv:
    context.ensure_folders()
    csv_file_name = os.path.join(context.output_folder,
                                 context.target.page_feed_output_file)
    with open(csv_file_name, 'w') as csv_file:
      writer = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
      writer.writerow(['Page URL', 'Custom label'])
      writer.writerows(values)
    logging.info(f'Generated page feed in {csv_file_name} file')

  sheets_client = sheets_utils.GoogleSpreadsheetUtils(context.credentials)
  sheets_client.update_values(context.target.page_feed_spreadsheetid, "A1:Z",
                              [['Page URL', 'Custom label']] + values)
  url = f'https://docs.google.com/spreadsheets/d/{context.target.page_feed_spreadsheetid}'
  logging.info('Generated page feed in Google Spreadsheet ' + url)

  elapsed = datetime.now() - ts_start
  logging.info(f'Finished "{step_name}" step, it took {elapsed}')
  return csv_file_name


def load_products(context: Context):
  products = execute_sql_query('get-products.sql', context)
  logging.info(f'Fetched {products.total_rows} products')
  return products


def create_or_update_adcustomizers(generate_csv: bool, context: Context) -> str:
  """Generate ad customizers (in Google Spreadsheet and CSV file)
    Args:
      generate_csv: generate CSV (True) or only update Spreadsheet (False)
    Returns:
      generated CSV file path
  """
  products = load_products(context)
  mgr = campaign_mgr.CampaignMgr(context, products)
  return mgr.generate_adcustomizers(generate_csv)


def generate_campaign(context: Context) -> str:
  """Generate campaign data for Ads Editor.
    Returns:
      generatd CSV file path relative to context.output_folder
  """
  step_name = 'campaign creation'
  ts_start = datetime.now()
  logging.info(f'Starting "{step_name}" step')
  products = load_products(context)
  output_path = None
  if products.total_rows:
    context.ensure_folders()
    output_path = campaign_mgr.generate_csv(context, products)
    logging.info(f'Generated campaign data for Ads Editor in {output_path}')
  elapsed = datetime.now() - ts_start
  logging.info(f'Finished "{step_name}" step, it took {elapsed}')
  return output_path


def execute(config: config_utils.Config, target: config_utils.ConfigTarget,
            cred, opts: ContextOptions):
  context = Context(config, target, cred, opts)

  validation = validate_config(context)
  if not validation['valid']:
    print(validation['message'] + 'Exiting')
    exit()

  context.ensure_folders()

  # #1 crete page feed
  create_or_update_page_feed(True, context)

  # #2 generate ad campaigns (with adcustomizers)
  output_file = generate_campaign(context)
  if not output_file:
    logging.warning(f"Couldn't generate campaign as no products found")
  else:
    logging.info('Creating a zip-archive')
    ts_start = datetime.now()
    image_folder = os.path.join(context.output_folder, context.image_folder)
    # archive output csv and images folder, archive's name will be the same as output csv
    arcfilename = os.path.join(
        context.output_folder,
        os.path.splitext(os.path.basename(output_file))[0] + '.zip')
    file_utils.zip_stream(arcfilename, [output_file, image_folder])
    #file_utils.zip(arcfilename, [output_file, image_folder])
    elapsed = datetime.now() - ts_start
    logging.info(
        f'Generated a zip-archive with campaign data and images in {arcfilename}, elapsed {elapsed}'
    )


def add_args(parser: argparse.ArgumentParser):
  parser.add_argument(
      '--target',
      dest='target',
      help=
      'Target name to generate artifacts for (by default all targets will be processed)'
  )
  parser.add_argument(
      '--output-folder',
      dest='output_folder',
      help=
      'Output folder path (relative to current dir or absolute) to place generated files into'
  )
  parser.add_argument(
      '--image-folder',
      dest='image_folder',
      help='Subfolder name/path of output folder to place product images into')
  parser.add_argument('--log-level',
                      dest='log_level',
                      help='Logging level: DEBUG, INFO, WARN, ERROR')
  parser.add_argument(
      '--images-dry-run',
      action="store_true",
      help=
      'If passed then images won\'t be downloaded and resized/padded (but image extensions still will be created)'
  )


def main():
  args = config_utils.parse_arguments(only_known=False, func=add_args)
  if args.log_level:
    logging.getLogger().setLevel(args.log_level)
  config = config_utils.get_config(args)
  pprint(vars(config))
  cred: credentials.Credentials = auth.get_credentials(args)
  opts = ContextOptions(args.output_folder or 'output',
                        args.image_folder,
                        images_dry_run=args.images_dry_run)
  if args.target:
    target = next(filter(lambda t: t.name == args.target, config.targets), None)
    execute(config, target, cred, opts)
  else:
    for target in config.targets:
      execute(config, target, cred, opts)


if __name__ == '__main__':
  main()
