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
from app.context import ContextOptions
import json
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
from common import config_utils, file_utils, bigquery_utils
from common.config_utils import ConfigError, ConfigErrorReason
from install import cloud_data_transfer
from common.auth import _SCOPES
from app.main import Context, create_or_update_page_feed, create_or_update_adcustomizers, generate_campaign, execute_sql_query, validate_config

logging.getLogger().setLevel(logging.INFO)

STATIC_DIR = os.getenv(
    'STATIC_DIR'
) or 'static'  # folder for static content relative to the current module

IS_GAE = os.getenv('GAE_APPLICATION')
OUTPUT_FOLDER = '/tmp'

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
config_on_gcs = config_file_name and config_file_name.startswith("gs://")


def copy_config_to_cache(config_file_name: str):
  # config is on GCS, copy it from GCS to local cache
  config_file_name_cache = os.path.join(OUTPUT_FOLDER,
                                        os.path.basename(config_file_name))
  try:
    file_utils.copy_file_from_gcs(config_file_name, config_file_name_cache)
    logging.info(
        f'Copied config {config_file_name} to local cache ({config_file_name_cache})'
    )
    args.config = config_file_name_cache
  except FileNotFoundError:
    # Application isn't initialized (no config), that's ok - let it to start
    config_file_name_cache = None


def _get_config() -> config_utils.Config:
  # it can throw FileNotFoundError if config is missing
  config = config_utils.get_config(args)
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

  # TODO: validate config/target
  for target in config.targets:
    context = Context(config, target, credentials,
                      ContextOptions(OUTPUT_FOLDER, 'images'))
    # Update page feed spreadsheet
    create_or_update_page_feed(False, context)

    # Update adcustomizers spreadsheet
    create_or_update_adcustomizers(False, context)

  return f"Updated feeds for all targets", 200


def create_context(target_name: str) -> Context:
  # for API (in contrast to main) we support only ADC auth
  credentials, project = google.auth.default(scopes=_SCOPES)
  config = _get_config()
  target_name = request.args.get('target')
  target = next(filter(lambda t: t.name == target_name, config.targets), None)
  context = Context(config, target, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images'))
  return context


@app.route("/api/pagefeed/generate")
def pagefeed_generate():
  target_name = request.args.get('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  output_file = create_or_update_page_feed(True, context)
  output_file = os.path.relpath(output_file, context.output_folder),
  return jsonify({
      "spreadsheet_id": context.target.page_feed_spreadsheetid,
      "filename": output_file,
      "feed_name": context.target.page_feed_name
  })


@app.route("/api/adcustomizers/generate", methods=["GET"])
def adcustomizers_generate():
  # for API (in contrast to main) we support only ADC auth
  target_name = request.args.get('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  output_file = create_or_update_adcustomizers(True, context)
  output_file = os.path.relpath(output_file, context.output_folder),
  return jsonify({
      "spreadsheet_id": context.target.adcustomizer_spreadsheetid,
      "filename": output_file,
      "feed_name": context.target.adcustomizer_feed_name
  })


@app.route("/api/campaign/generate", methods=["GET"])
def campaign_generate():
  target_name = request.args.get('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  output_file = generate_campaign(context)
  if not output_file:
    return jsonify({
        "error": "Couldn't generate a ad campaign because no products found"
    }), 500
  # archive output csv and images folder
  output_folder_rel = os.path.relpath(os.path.dirname(output_file),
                                      context.output_folder)
  image_folder = os.path.join(context.output_folder, output_folder_rel,
                              context.image_folder)
  arcfilename = os.path.join(
      OUTPUT_FOLDER,
      os.path.splitext(os.path.basename(output_file))[0] + '.zip')
  file_utils.zip(arcfilename, [output_file, image_folder])
  return jsonify({"filename": os.path.basename(arcfilename)})


@app.route("/api/labels", methods=["GET"])
def get_labels():
  target_name = request.args.get('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  labels = execute_sql_query('get-labels.sql', context)
  result = []
  for row in labels:
    obj = {}
    for col, val in row.items():
      obj[col] = val
    result.append(obj)
  return jsonify(result)


@app.route("/api/products", methods=["GET"])
def get_products():
  target_name = request.args.get('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  products = execute_sql_query('get-products.sql', context)
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
  return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


def return_api_config_error(error: ConfigError):
  return jsonify(
      error=error.to_dict(),
      config_file=config_file_name,
  ), 500


@app.route("/api/validate", methods=["GET"])
def validate_env():
  try:
    config = _get_config()
  except FileNotFoundError:
    error = ConfigError(
        reason=ConfigErrorReason.NOT_INITIALIZED,
        description="Application is not initialized: config file not found")
    return return_api_config_error(error)
  credentials, project = google.auth.default(scopes=_SCOPES)
  context = Context(config, None, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images'))

  # ok, config exists, check its content
  errors = config.validate(generation=False, validate_targets=False)
  if len(errors):
    msg = "\n".join([e.error for e in errors])
    return return_api_config_error(
        ConfigError(reason=ConfigErrorReason.NOT_INITIALIZED,
                    description="Application is not initialized: " + msg))

  # ok, config seems correct (at least for DT), check BQ dataset
  dataset = context.bq_client.get_dataset(config.dataset_id)
  if not dataset:
    return return_api_config_error(
        ConfigError(
            reason=ConfigErrorReason.NOT_INITIALIZED,
            description=
            f"Application is not initialized: Data Transfer dataset '{config.dataset_id}'' not found)"
        ))
  # ok, dataset exists, check Data Transfer (existence, state, schedule)
  data_transfer = cloud_data_transfer.CloudDataTransferUtils(
      config.project_id, config.dataset_location, credentials)
  try:
    transfer_config = data_transfer.check_merchant_center_transfer(
        config.merchant_id, config.dataset_id)
  except cloud_data_transfer.DataTransferError as e:
    return return_api_config_error(
        ConfigError(reason=ConfigErrorReason.NOT_INITIALIZED,
                    description=f"Application is not initialized: {e}"))
  # ok, DT is correct, check that config contains at least one target and that target is valid
  if len(config.targets) == 0:
    return return_api_config_error(
        ConfigError(ConfigErrorReason.INVALID_CONFIG, f'No target found'))

  # now we'll check all targets by fetching data from our custom view (Products_Filtered_{target})
  for target in config.targets:
    try:
      context.target = target
      labels = execute_sql_query('get-labels.sql', context)
    except Exception as e:
      return return_api_config_error(
          ConfigError(ConfigErrorReason.NOT_INITIALIZED,
                      f"Application is not initialized: failed to load labels for target '{target.name}' - {e}"))
  # finally, GCP configuration seems OK but there could be some violation/warnings in config
  try:
    response = validate_config(context)
    errors = response['errors']
  except:
    # if app wasn't initialized then validate_config will fails (it loads labels from BQ)
    errors = context.config.validate(generation=True, validate_targets=True)
  return jsonify(errors=errors)


@app.route("/api/config", methods=["GET"])
def get_config():
  # 1. проверить что конфиг вообще есть - если его нет, приложение в stage 0 - "non initialized"
  #   имя конфиг файла может быть не задано, используется config.json по умолчанию, но тогда в режиме readonly
  # 2. если конфиг есть - в нем должно быть минимум merchan_id и dataset_id
  #    (merchant_id может быть GMC или листовой. Если он GMC (корневой), то дополнительный id могут быть заданы)
  # 3. проверить, что DT создан и последний запуск был удачный, получить дату/время следующего запуска
  # 4. проверить параметры для генерации кампаний (validate_config)
  #   - dsa_website
  #   - spreadsheet'ы созданы для pagefeed и кастомайзеров
  #   - описания заданы для категорий (label -> description)

  # if we're in GAE and config file is local then we're in readonly mode (as we can't update that file on disk)
  readonly = IS_GAE and not config_on_gcs
  try:
    config = _get_config()
  except FileNotFoundError:
    if readonly:
      error = ConfigError(
          reason=ConfigErrorReason.INVALID_DEPLOYMENT,
          description=
          "The application uses a local config file and it does not exist")
    else:
      error = ConfigError(
          reason=ConfigErrorReason.NOT_INITIALIZED,
          description="Application is not initialized: config file not found")
    return return_api_config_error(error)

  credentials, project = google.auth.default(scopes=_SCOPES)
  context = Context(config, None, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images'))

  # ok, config exists, check its validity
  try:
    response = validate_config(context)
    errors = response['errors']
  except:
    # if app wasn't initialized then validate_config will fails (it loads labels from BQ)
    errors = context.config.validate(generation=True, validate_targets=True)

  # TODO commit_link = 'https://github.com/google/product-dsa/commit/' + os.environ.get('GIT_COMMIT')
  commit = os.getenv('GIT_COMMIT') or ''
  if commit:
    commit = 'https://professional-services.googlesource.com/solutions/product-dsa/+/' + commit

  return jsonify(config=config.to_dict(),
                 config_file=config_file_name,
                 commit_link=commit,
                 errors=errors)


@app.route("/api/config", methods=["POST"])
def post_config():
  new_config = request.get_json(cache=False)
  # we can update config if and only if it's stored on GCS (i.e. args.config has a gcs url)
  if (config_file_name and config_file_name.startswith("gs://")):
    #content = yaml.dump(new_config, allow_unicode=True)
    content = json.dumps(new_config)
    file_utils.save_file_to_gcs(config_file_name, content)
    # and update the local cache in /tmp
    if (args.config == config_file_name):
      # this means that the config wasn't copied to /tmp on start (because it didn't exist)
      copy_config_to_cache()
    else:
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


# copy config from GCS to local cache
if config_on_gcs:
  # config is on GCS, copy it from GCS to local cache
  copy_config_to_cache()

if __name__ == '__main__':
  # NOTE: we run server.py directly only during development, normally it's run by gunicorn in GAE
  parser = argparse.ArgumentParser()
  parser.add_argument('--debug', action='store_true')
  srv_args = parser.parse_known_args()[0]
  app.run(debug=srv_args.debug)  # run our Flask app
