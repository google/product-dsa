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
import yaml
import os
import argparse
import logging
import decimal
from pprint import pprint
from flask import Flask, request, jsonify, send_from_directory
from flask.json import JSONEncoder
import google.auth
from google.auth.transport import requests
from google.oauth2 import id_token
from common import config_utils, file_utils
from common.auth import _SCOPES
from app.main import create_or_update_page_feed, create_or_update_adcustomizers, generate_campaign, execute_sql_query, validate_config

logging.getLogger().setLevel(logging.INFO)

STATIC_DIR = os.getenv('STATIC_DIR') or 'static' # folder for static content relative to the current module

app = Flask(__name__)


class JsonEncoder(JSONEncoder):
  def default(self, obj):
    if isinstance(obj, decimal.Decimal):
      return float(obj)
    return JSONEncoder.default(self, obj)


app.json_encoder = JsonEncoder


args = config_utils.parse_arguments(only_known=True)
config_file_name = config_utils.get_config_url(args)
args.config = config_file_name
# copy config from GCS to local cache
if (config_file_name and config_file_name.startswith("gs://")):
  # config is on GCS, copy it from GCS to local cache
  config_file_name_cache = '/tmp/' + os.path.basename(config_file_name)
  file_utils.copy_file_from_gcs(config_file_name, config_file_name_cache)
  logging.info(
      f'Copied config {config_file_name} to local cache ({config_file_name_cache})')
  args.config = config_file_name_cache


def _get_config() -> config_utils.Config:
  config = config_utils.get_config(args)
  config.output_folder = '/tmp'
  return config


def _verify_token(config: config_utils.Config):
  bearer_token = request.headers.get('Authorization')
  if not bearer_token:
    return
  token = bearer_token.split(' ')[1]
  claim = id_token.verify_oauth2_token(token, requests.Request())
  pprint(claim)
  if claim[
      'email'] != f'{config.project_id}@appspot.gserviceaccount.com' or not claim[
          'email_verified']:
    raise Exception('Access denied')


@app.route("/api/update", methods=["POST", "GET"])
def update_feeds():
  """Endpoint to be call by Pub/Sub message from DT completion to trigger feeds updating"""
  config = _get_config()
  # Verify the Cloud Pub/Sub-generated JWT in the "Authorization" header.
  try:
    _verify_token(config)
  except Exception as e:
    return str(e), 401

  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)

  context = {'xcom': {}, 'gcp_credentials': credentials}
  # Update page feed spreadsheet
  create_or_update_page_feed(False, config, context)

  # Update adcustomizers spreadsheet
  create_or_update_adcustomizers(False, config, context)

  return f"Updated pagefeed in https://docs.google.com/spreadsheets/d/{config.page_feed_spreadsheetid}", 200


@app.route("/api/pagefeed/generate")
def pagefeed_generate():
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)
  config = _get_config()
  context = {'xcom': {}, 'gcp_credentials': credentials}
  create_or_update_page_feed(True, config, context)
  return jsonify({
      "spreadsheet_id": config.page_feed_spreadsheetid,
      "filename": config.page_feed_output_file,
      "feed_name": config.page_feed_name
  })


@app.route("/api/adcustomizers/generate", methods=["GET"])
def adcustomizers_generate():
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)
  config = _get_config()
  context = {'xcom': {}, 'gcp_credentials': credentials}
  create_or_update_adcustomizers(True, config, context)
  return jsonify({
      "spreadsheet_id": config.adcustomizer_spreadsheetid,
      "filename": config.adcustomizer_output_file,
      "feed_name": config.adcustomizer_feed_name
  })


@app.route("/api/campaign/generate", methods=["GET"])
def campaign_generate():
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)
  context = {'xcom': {}, 'gcp_credentials': credentials}
  config = _get_config()
  output_file = generate_campaign(config, context)
  # archive output csv and images folder
  image_folder = os.path.join(config.output_folder, config.image_folder)
  arcfilename = os.path.join(
      config.output_folder,
      os.path.splitext(os.path.basename(output_file))[0] + '.zip')
  file_utils.zip(arcfilename, [output_file, image_folder])
  return jsonify({"filename": os.path.basename(arcfilename)})


@app.route("/api/labels", methods=["GET"])
def get_labels():
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)
  config = _get_config()
  context = {'xcom': {}, 'gcp_credentials': credentials}
  labels = execute_sql_query('get-labels.sql', config, context)
  result = []
  for row in labels:
    obj = {}
    for col, val in row.items():
      obj[col] = val
    result.append(obj)
  return jsonify(result)


@app.route("/api/products", methods=["GET"])
def get_products():
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)
  config = _get_config()
  context = {'xcom': {}, 'gcp_credentials': credentials}
  products = execute_sql_query('get-products.sql', config, context)
  result = []
  for row in products:
    obj = {}
    for col, val in row.items():
      obj[col] = val
    result.append(obj)
  return jsonify(result)


@app.route("/api/download", methods=["GET"])
def download_file():
  filename = request.args.get('filename')
  if not filename:
    return "No file name was provided", 400
  config = _get_config()
  return send_from_directory(config.output_folder,
                             filename,
                             as_attachment=True)


@app.route("/api/config", methods=["GET"])
def get_config():
  config = _get_config()
  commit = os.getenv('GIT_COMMIT') or ''
  config_file_name = args.config or os.environ.get('CONFIG')
  credentials, project = google.auth.default(scopes=_SCOPES)
  context = {'xcom': {}, 'gcp_credentials': credentials}
  response = validate_config(config, context)
  # TODO commit_link = 'https://github.com/google/product-dsa/commit/' + os.environ.get('GIT_COMMIT')
  if commit:
    commit = 'https://professional-services.googlesource.com/solutions/product-dsa/+/' + commit
  return jsonify(config=config.__dict__,
                 config_file=config_file_name,
                 commit_link=commit,
                 errors=response['msg'])


@app.route("/api/config", methods=["POST"])
def post_config():
  new_config = request.get_json(cache=False)
  # we can update config if and only if it's stored on GCS (i.e. args.config has a gcs url)
  if (config_file_name and config_file_name.startswith("gs://")):
    content = yaml.dump(new_config, allow_unicode=True)
    file_utils.save_file_to_gcs(config_file_name, content)
    # and update the local cache in /tmp
    file_utils.save_file_content(args.config, content)
    return 'Config updated', 200
  else:
    msg = f'Updating config is not possible because it is not stored on GCS'
    logging.warning(msg)
    return msg, 400


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
  # NOTE: we don't use Flusk standard support for static files
  # (static_folder option and send_static_file method)
  # because they can't distinguish requests for static files (js/css) and client routes (like /products)
  file_requested = os.path.join(app.root_path, STATIC_DIR, path)
  if not os.path.isfile(file_requested):
    path = "index.html"
  return send_from_directory(STATIC_DIR, path)


if __name__ == '__main__':
  # NOTE: we run server.py directly only during development, normally it's run by gunicorn in GAE
  parser = argparse.ArgumentParser()
  parser.add_argument('--debug', action='store_true')
  srv_args = parser.parse_known_args()[0]
  app.run(debug=srv_args.debug)  # run our Flask app
