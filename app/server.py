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
import os
import logging
from pprint import pprint
from flask import Flask, request
import google.auth
from google.auth.transport import requests
from google.oauth2 import id_token
from common import config_utils
from common.auth import _SCOPES
from app.main import create_or_update_page_feed, execute_sql_query
from app.campaign_mgr import CampaignMgr

logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__)

args = config_utils.parse_arguments(only_known=True)
# configuration values either go from config file on GCS or from env vars
config = config_utils.get_config(args)
pprint(vars(config))


def verify_token():
  bearer_token = request.headers.get('Authorization')
  if not bearer_token:
    return
  token = bearer_token.split(' ')[1]
  claim = id_token.verify_oauth2_token(token, requests.Request())
  pprint(claim)
  if claim['email'] != f'{config.project_id}@appspot.gserviceaccount.com' or not claim['email_verified']:
    raise Exception('Access denied')


@app.route("/pagefeed/update", methods=["POST", "GET"])
def pagefeed_update():
  # Verify the Cloud Pub/Sub-generated JWT in the "Authorization" header.
  try:
    verify_token()
  except Exception as e:
    return str(e), 401

  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)

  context = {'xcom': {}, 'gcp_credentials': credentials}
  # Update page feed spreadsheet
  create_or_update_page_feed(False, config, context)

  # Update adcustomizers spreadsheet
  update_adcustomizers(config, context)

  return f"Updated pagefeed in https://docs.google.com/spreadsheets/d/{config.page_feed_spreadsheetid}", 200


def update_adcustomizers(config: config_utils.Config, context):
  products = execute_sql_query('get-products.sql', config, context)
  if products.total_rows == 0:
    logging.info('Skipping ad-customizer updating as there\'s no products')
    return

  campaign_mgr = CampaignMgr(config, products, context['gcp_credentials'])
  campaign_mgr.generate_adcustomizers(generate_csv=False)


if __name__ == '__main__':
  app.run()  # run our Flask app
