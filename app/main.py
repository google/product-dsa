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
import logging
from typing import Dict, List
import time
import os
import csv
from google.auth import credentials
from pprint import pprint
from common import auth, config_utils, sheets_utils, file_utils
from app import wf_execute_sql
from app import campaign_mgr

logging.getLogger().setLevel(logging.INFO)


def execute_sql_query(name: str,
                      config: config_utils.Config,
                      context: Dict,
                      macros: Dict = None):
  cfg = {
      'sql_file': './sql/' + name,
      'project_id': config.project_id,
      'macros': {
          'project_id': config.project_id,
          'dataset': config.dataset_id,
          'merchant_id': config.merchant_id,
      }
  }
  return wf_execute_sql.run(cfg, context)


def validate_config(config: config_utils.Config, context):
  error_details =[]
  err_message = ''
  if not config.merchant_id:
    err_message = 'No merchant_id found in configuration'
    error_details.append({'field': 'merchant_id', 'error': err_message})
  if not config.page_feed_spreadsheetid:
    err_message = 'No spreadsheet id for page feed found in configuration'
    error_details.append({'field': 'page_feed_spreadsheetid', 'error': err_message})
  if not config.dsa_website:
    err_message = 'No DSA website found in configuration'
    error_details.append({'field': 'dsa_website', 'error': err_message})

  category_labels = execute_sql_query('get-category-labels.sql', config,
                                      context)
  missing_category_desc = False
  if category_labels.total_rows:
    for row in category_labels:
      desc = config.category_ad_descriptions.get(row[0])
      if not desc or desc == '':
        missing_category_desc = True
        err_message = f'Missing category description for \'{row[0]}\' in configuration\n'

    if missing_category_desc:
      err_message += 'Update the missing categories in the config.yaml file'
      error_details.append({
          'field': 'category_ad_descriptions',
          'error': err_message
      })

  if error_details:
    message = ''
    for err in error_details:
      message += (err['field'] + ': ' + err['error'] + '\n')
    print (message + 'Exiting')
    return {'valid': False, 'msg': error_details}
  return {'valid': True, 'msg': []}


def create_or_update_page_feed(generate_csv: bool, config: config_utils.Config,
                               context: Dict):
  step_name = 'page feed ' + ('creation' if generate_csv else 'updating')
  t0 = time.time()
  ts = time.strftime('%H:%M:%S')
  # Execute a SQL script (TODO: read its name from config) to get data for DSA page feed
  # The contract for the script:
  #   we expect 2-columns: 'Page_URL' and 'Custom_label'
  #   both columns should be empty or NULL
  #   the Custom_label column can contain one or many label, separated by ';'
  #   values in Page_URL column should be unique
  # NOTE: currently we don't validate all those invariants, only assume they
  logging.info(f'[{ts}] Starting "{step_name}" step')
  data = execute_sql_query('create-page-feed.sql', config, context)
  logging.info(f'Page-feed query returned {data.total_rows} rows')

  values = []
  for row in data:
    values.append([row[0], row[1]])

  if generate_csv:
    csv_file_name = os.path.join(config.output_folder,
                                 config.page_feed_output_file)
    with open(csv_file_name, 'w') as csv_file:
      writer = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
      writer.writerow(['Page URL', 'Custom label'])
      writer.writerows(values)
    logging.info(f'Generated page feed in {csv_file_name} file')

  sheets_client = sheets_utils.GoogleSpreadsheetUtils(
      context['gcp_credentials'])
  sheets_client.update_values(config.page_feed_spreadsheetid, "Main!A1:Z",
                              [['Page URL', 'Custom label']] + values)
  url = f'https://docs.google.com/spreadsheets/d/{config.page_feed_spreadsheetid}'
  logging.info('Generated page feed in Google Spreadsheet ' + url)

  elapsed = time.time() - t0
  logging.info(f'Finished "{step_name}" step, it took {elapsed} sec')


def create_or_update_adcustomizers(generate_csv: bool,
                                   config: config_utils.Config, context):
  products = execute_sql_query('get-products.sql', config, context)
  if products.total_rows == 0:
    logging.info('Skipping ad-customizer updating as there\'s no products')
    return

  mgr = campaign_mgr.CampaignMgr(config, products, context['gcp_credentials'])
  mgr.generate_adcustomizers(generate_csv)


def generate_campaign(config: config_utils.Config, context) -> str:
  step_name = 'campaign creation'
  t0 = time.time()
  ts = time.strftime('%H:%M:%S')
  logging.info(f'[{ts}] Starting "{step_name}" step')
  products = execute_sql_query('get-products.sql', config, context)
  logging.info(f'Fetched {products.total_rows} products')
  output_path = ''
  if products.total_rows:
    output_path = campaign_mgr.generate_csv(config, products,
                                            context['gcp_credentials'])
    logging.info(f'Generated campaing data for Ads Editor in {output_path}')
  elapsed = time.time() - t0
  logging.info(f'Finished "{step_name}" step, it took {elapsed} sec')
  return output_path


def main():
  args = config_utils.parse_arguments()
  config = config_utils.get_config(args)
  pprint(vars(config))
  cred: credentials.Credentials = auth.get_credentials(args)

  context = {'xcom': {}, 'gcp_credentials': cred}

  if not validate_config(config, context)['valid']:
    exit()

  if config.output_folder and not os.path.exists(config.output_folder):
    os.mkdir(config.output_folder)

  # #1 crete page feed
  create_or_update_page_feed(True, config, context)

  # #2 generate ad campaigns (with adcustomizers)
  output_file = generate_campaign(config, context)
  image_folder = os.path.join(config.output_folder, config.image_folder)

  # archive output csv and images folder
  arcfilename = os.path.join(
      config.output_folder,
      os.path.splitext(os.path.basename(output_file))[0] + '.zip')
  file_utils.zip(arcfilename, [output_file, image_folder])
  logging.info(f'Generated archive zip campaign data and images in {arcfilename}')


if __name__ == '__main__':
  main()
