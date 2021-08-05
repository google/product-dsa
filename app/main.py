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
import time
from google.auth import credentials
from pprint import pprint
from common import auth, config_utils
import wf_execute_sql


def validate_config(config: config_utils.Config):
  if (not config.merchant_id):
    print('No merchant_id was defined, exiting')
    exit()


def create_page_feed(config: config_utils.Config, context):

  step_name = 'page feed creation'
  t0 = time.time()
  ts = time.strftime('%H:%M:%S %z')
  print(f'[{ts}] Starting "{step_name}" step')
  cfg = {
    'sql_file': 'scripts/create-page-feed.sql',
    'project_id': config.project_id,
    'macros': {
      'project_id': config.project_id,
      'dataset': config.dataset_id,
      'merchant_id': config.merchant_id,
    }
  }
  data = wf_execute_sql.run(cfg, context)
  context['page-feed-data'] = data
  print('Returned {data.total_rows} rows')
  with open('page-feed.csv', 'w') as csv_file:
    csv_file.write('Page_URL,pdsa_custom_labels\n')
    for row in data:
      csv_file.write(row['Page_URL'] + ',' + row['pdsa_custom_labels'] + '\n')
  elapsed = time.time() - t0
  print(f'Finished "{step_name}" step, it took {elapsed} sec')


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

  # #1 creating page feed
  create_page_feed(config, context)
  # TODO: support updating
  #   generate a CSV with data from pagefeed

  # #2 generating ad campaigns
  # TODO: fetch data from context['xcom']['pagefeed-table'] table and generate CSV with data for Ads Editor
  generate_campaign_for_adeditor(config, context)


if __name__ == '__main__':
  main()
