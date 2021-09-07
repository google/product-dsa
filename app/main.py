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
from common import auth, config_utils, sheets_utils
from app import wf_execute_sql
from app import campaign_mgr

logging.getLogger().setLevel(logging.INFO)


def execute_sql_query(name: str,
                      config: config_utils.Config,
                      context: Dict,
                      macros: Dict = None):
  cfg = {
      'sql_file': './scripts/' + name,
      'project_id': config.project_id,
      'macros': {
          'project_id': config.project_id,
          'dataset': config.dataset_id,
          'merchant_id': config.merchant_id,
      }
  }
  return wf_execute_sql.run(cfg, context)


def validate_config(config: config_utils.Config, context):
  if (not config.merchant_id):
    print('No merchant_id found in configuration (merchant_id), exiting')
    exit()
  if (not config.page_feed_spreadsheetid):
    print(
        'No spreadsheet id for page feed found in configuration (page_feed_spreadsheetid), exiting'
    )
    exit()
  if (not config.dsa_website):
    print('No DSA website found in configuration (dsa_website), exiting')
    exit()

  category_labels = execute_sql_query('get-category-labels.sql', config,
                                      context)
  missing_category_desc = False
  if category_labels.total_rows:
    for row in category_labels:
      desc = config.category_ad_descriptions.get(row[0])
      if not desc or desc == '':
        missing_category_desc = True
        print(
            f'Missing category description for \'{row[0]}\' in configuration (category_ad_descriptions)'
        )
    if missing_category_desc:
      print('Update the missing categories in the config.yaml file, exiting')
      exit()


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
    csv_file_name = os.path.join(
        config.output_folder or '', config.page_feed_output_file or
        'page-feed.csv')
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


def generate_campaign(config: config_utils.Config, context):
  step_name = 'campaign creation'
  t0 = time.time()
  ts = time.strftime('%H:%M:%S')
  logging.info(f'[{ts}] Starting "{step_name}" step')
  products = execute_sql_query('get-products.sql', config, context)
  logging.info(f'Fetched {products.total_rows} products')
  if products.total_rows:
    output_path = campaign_mgr.generate_csv(config, products,
                                            context['gcp_credentials'])
    logging.info(f'Generated campaing data for Ads Editor in {output_path}')
  elapsed = time.time() - t0
  logging.info(f'Finished "{step_name}" step, it took {elapsed} sec')


def main():
  args = config_utils.parse_arguments()
  config = config_utils.get_config(args)
  pprint(vars(config))
  cred: credentials.Credentials = auth.get_credentials(args)

  context = {'xcom': {}, 'gcp_credentials': cred}
  validate_config(config, context)

  if config.output_folder and not os.path.exists(config.output_folder):
    os.mkdir(config.output_folder)

  # #1 crete page feed
  create_or_update_page_feed(True, config, context)

  # #2 generate ad campaigns (with adcustomizers)
  generate_campaign(config, context)


if __name__ == '__main__':
  # TODO: support commands: create | update | install
  main()
