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
from google.auth import credentials
from pprint import pprint
from common import auth, config_utils, sheets_utils
import wf_execute_sql

logging.getLogger().setLevel(logging.INFO)

def validate_config(config: config_utils.Config):
  if (not config.merchant_id):
    print('No merchant_id found in configuration (merchant_id), exiting')
    exit()
  if (not config.page_feed_spreadsheetid):
    print('No spreadsheet id for page feed found in configuration (page_feed_spreadsheetid), exiting')
    exit()


def create_page_feed(config: config_utils.Config, context: Dict):
  step_name = 'page feed creation'
  t0 = time.time()
  ts = time.strftime('%H:%M:%S %z')
  # Execute a SQL script (TODO: read its name from config) to get data for DSA page feed
  # The contract for the script:
  #   we expect 2-columns: 'Page_URL' and 'Custom_label'
  #   both columns should be empty or NULL
  #   the Custom_label column can contain one or many label, separated by ';'
  #   values in Page_URL column should be unique
  # NOTE: currently we don't validate all those invariants, only assume they
  print(f'[{ts}] Starting "{step_name}" step')
  cfg = {
    'sql_file': './scripts/create-page-feed.sql',
    'project_id': config.project_id,
    'macros': {
      'project_id': config.project_id,
      'dataset': config.dataset_id,
      'merchant_id': config.merchant_id,
    }
  }
  data = wf_execute_sql.run(cfg, context)
  context['page-feed-data'] = data
  logging.info('Page-feed query returned {data.total_rows} rows')

  values = []
  for row in data:
    values.append([row[0], row[1]])

  sheets_client = sheets_utils.GoogleSpreadsheetUtils(context['gcp_credentials'])

  with open('page-feed.csv', 'w') as csv_file:
    csv_file.write('Page URL,Custom label\n')
    for row in values:
      csv_file.write(",".join(str(item) for item in row) + "\n")
  url = f'https://docs.google.com/spreadsheets/d/1{config.page_feed_spreadsheetid}'
  logging.info('Generated page feed in Google Spreadsheet ' + url)

  sheets_client.update_values(config.page_feed_spreadsheetid, "Main!A1:Z",
      [['Page URL', 'Custom label']] + values)
  logging.info('Generated page feed in page-feed.csv file')

  elapsed = time.time() - t0
  logging.info(f'Finished "{step_name}" step, it took {elapsed} sec')


def generate_campaign_for_adeditor(config: config_utils.Config, context):
  page_feed_data = context['page-feed-data']
  # TODO
  pass


def main():
  args = config_utils.parse_arguments()
  config = config_utils.get_config(args)
  pprint(vars(config))
  cred: credentials.Credentials = auth.get_credentials(args)

  validate_config(config)
  context = {'xcom': {}, 'gcp_credentials': cred}

  # #1 crete page feed
  create_page_feed(config, context)

  # #2 generate ad campaigns
  generate_campaign_for_adeditor(config, context)


if __name__ == '__main__':
  # TODO: support commands: create | update | install
  main()
