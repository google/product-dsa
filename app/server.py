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
import flask
import google.auth
from pprint import pprint
from common import config_utils
from common.auth import _SCOPES
from app.main import create_or_update_page_feed

app = flask.Flask(__name__)


@app.route("/pagefeed/update", methods=["POST", "GET"])
def pagefeed_update():
  args = config_utils.parse_arguments(only_known=True)
  # configuration values either go from config file on GCS or from env vars
  config = config_utils.get_config(args)
  pprint(vars(config))
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)

  context = {'xcom': {}, 'gcp_credentials': credentials}

  # Update page feed spreadsheet
  create_or_update_page_feed(False, config, context)
  return f"Updated pagefeed in https://docs.google.com/spreadsheets/d/{config.page_feed_spreadsheetid}", 200


if __name__ == '__main__':
  app.run()  # run our Flask app
