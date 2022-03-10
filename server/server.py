# coding=utf-8
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
from google import oauth2
import json
import os
import argparse
import logging
import decimal
from datetime import datetime
from pprint import pprint
from flask import Flask, request, jsonify, send_from_directory, Response
from flask.json import JSONEncoder
from flask_cors import CORS
from google.auth.transport import requests
from google.oauth2 import id_token
from google.cloud.resourcemanager_v3.services.projects import ProjectsClient
import zipstream
from smart_open import open
from app.context import ContextOptions
from app.main import Context, create_or_update_page_feed, create_or_update_adcustomizers, generate_campaign, validate_config
from common import config_utils, file_utils, sheets_utils
from common.config_utils import ApplicationError, ApplicationErrorReason
from common.auth import get_credentials
from install import cloud_data_transfer, cloud_env_setup

# NOTE: this module's code is executed each time when a new worker started, so keep it small
# To handle instance start up see `on_instance_start` method

loglevel = os.getenv('LOG_LEVEL') or 'INFO'
logging.getLogger().setLevel(loglevel)
logging.getLogger('smart_open.gcs').setLevel(logging.WARNING)
logging.getLogger('smart_open.smart_open_lib').setLevel(logging.WARNING)

STATIC_DIR = os.getenv(
    'STATIC_DIR'
) or 'static'  # folder for static content relative to the current module

app = Flask(__name__)
CORS(app)

IS_GAE = os.getenv('GAE_APPLICATION')
OUTPUT_FOLDER = '/tmp' if IS_GAE else os.path.abspath(
    os.path.join(app.root_path, './../output'))

MAX_RESPONSE_SIZE = 32 * 1024 * 1024  #if IS_GAE else XXX


class JsonEncoder(JSONEncoder):

  def default(self, obj):
    if isinstance(obj, decimal.Decimal):
      return float(obj)
    return JSONEncoder.default(self, obj)


app.json_encoder = JsonEncoder

args = config_utils.parse_arguments(only_known=True)
config_file_name = config_utils.get_config_url(args)
args.config = config_file_name  # NOTE: we'll overwrite args.config in copy_config_to_cache
config_on_gcs = config_file_name and config_file_name.startswith("gs://")
expected_audience = ''
g_setup_lock = file_utils.SetupExecLock(OUTPUT_FOLDER)



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
    logging.warn(
        'Could not copy config file to a local cache because the file was not found'
    )
    # Application isn't initialized (no config), that's ok - let it to start
    config_file_name_cache = None


def _get_config() -> config_utils.Config:
  # it can throw FileNotFoundError if config is missing
  config = config_utils.get_config(args)
  return config


def _get_credentials():
  credentials = get_credentials(args)
  return credentials


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
  return claim


def _validate_iap_jwt() -> str:
  """Validate an IAP JWT.

    Args:
      iap_jwt: The contents of the X-Goog-IAP-JWT-Assertion header.
      expected_audience: The Signed Header JWT audience. See
          https://cloud.google.com/iap/docs/signed-headers-howto
          for details on how to get this value.

    Returns:
      user_email
    """
  iap_jwt = request.headers.get('X-Goog-IAP-JWT-Assertion')
  if not iap_jwt:
    raise Exception(
        "No IAP header found. Probably you're running server out of Google Cloud or disable IAP for GAE"
    )

  try:
    decoded_jwt = id_token.verify_token(
        iap_jwt,
        requests.Request(),
        audience=expected_audience,
        certs_url='https://www.gstatic.com/iap/verify/public_key')
    logging.info(f'Validated IAP user {decoded_jwt["email"]}')
    return decoded_jwt['email']
    #(decoded_jwt['sub'], decoded_jwt['email'], '')
  except Exception as e:
    raise Exception(f'JWT validation error: {e}') from e


def _get_req_arg_bool(name: str):
  arg = request.args.get(name)
  if not arg:
    return False
  return arg.upper() == 'TRUE' or arg == '1'


def _get_req_arg_str(name: str):
  arg = request.args.get(name)
  if not arg or arg == 'null' or arg == 'undefined':
    return None
  return str(arg)


@app.route("/api/update", methods=["POST", "GET"])
def update_feeds():
  """Endpoint to be call by Pub/Sub message from DT completion to trigger feeds updating"""
  if g_setup_lock.is_locked():
    logging.info('Skipping feeds update as setup is executing')
    return 'Update skipped as setup is executing', 200

  config = _get_config()
  # Verify the Cloud Pub/Sub-generated JWT in the "Authorization" header.
  try:
    _verify_token(config)
  except Exception as e:
    app.logger.exception(e)
    return str(e), 401

  # for API (in contrast to main) we support only ADC auth
  credentials = _get_credentials()
  context = Context(config, None, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images'))
  validation = validate_config(context)
  logging.debug(f'update_feeds: config validated ({validation["valid"]})')
  if not validation['valid']:
    error = ApplicationError(
        reason=ApplicationErrorReason.INVALID_CONFIG,
        description=f"There errors in configuration: {validation['message']}")
    logging.info(f"update_feeds: There errors in configuration: {validation['message']}")
    return return_api_config_error(error)

  logging.debug('Starting updating feeds for all targets')
  for target in config.targets:
    # NOTE: context.output_folder will be left not initialized (not joined with target),
    # but it's OK as we aren't generating any files here
    context.target = target
    # Update page feed spreadsheet
    create_or_update_page_feed(False, context)

    # Update adcustomizers spreadsheet
    create_or_update_adcustomizers(False, context)

  logging.info('All feeds for all targets were successfully updated')
  return f"Updated feeds for all targets", 200


def create_context(target_name: str) -> Context:
  # for API (in contrast to main) we support only ADC auth
  credentials = _get_credentials()
  config = _get_config()
  target_name = _get_req_arg_str('target')
  target = next(filter(lambda t: t.name == target_name, config.targets), None)
  context = Context(config, target, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images', images_on_gcs=IS_GAE))
  return context


@app.route("/api/pagefeed/generate")
def pagefeed_generate():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  target_name = _get_req_arg_str('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  validation = validate_config(context)
  if not validation['valid']:
    error = ApplicationError(
        reason=ApplicationErrorReason.INVALID_CONFIG,
        description=
        f"There errors in configuration for the selected target {target_name}: {validation['message']}"
    )
    return return_api_config_error(error)

  output_file = create_or_update_page_feed(True, context)
  output_file = os.path.relpath(output_file, OUTPUT_FOLDER)
  return jsonify({
      "spreadsheet_id": context.target.page_feed_spreadsheetid,
      "filename": output_file,
      "feed_name": context.target.page_feed_name
  })


@app.route("/api/adcustomizers/generate", methods=["GET"])
def adcustomizers_generate():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  target_name = _get_req_arg_str('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  validation = validate_config(context)
  if not validation['valid']:
    error = ApplicationError(
        reason=ApplicationErrorReason.INVALID_CONFIG,
        description=
        f"There errors in configuration for the selected target {target_name}: {validation['message']}"
    )
    return return_api_config_error(error)
  output_file = create_or_update_adcustomizers(True, context)
  output_file = os.path.relpath(output_file, OUTPUT_FOLDER)
  return jsonify({
      "spreadsheet_id": context.target.adcustomizer_spreadsheetid,
      "filename": output_file,
      "feed_name": context.target.adcustomizer_feed_name
  })


def _generate_gcs_download_url(gcs_url: str, credentials,
                               storage_client) -> str:
  # NOTE: to create a signedUrl for GCS object we need to be autheticated as SA
  # if it's not the case (e.g. running locally w/o a SA key file), then just return the GCS url
  if hasattr(credentials, 'service_account_email'):
    try:
      url = file_utils.gcs_get_signed_url(client=storage_client,
                                          url=gcs_url,
                                          credentials=credentials)
      logging.info(f'Created a GCS signed url for download: {url}')
    except Exception as e:
      # NOTE: this is not normal, but it'd be very unfortunate for the user to get an exception at the very end of waiting
      logging.exception(e)
      logging.error(
          f'Failure on GCS signed url creation, returning a raw GCS url instead'
      )
      url = gcs_url
  else:
    url = gcs_url
    logging.info(
        f'Impossible to create a GCS signed url (no service account), returning a GCS path {url}'
    )
  return url


@app.route("/api/campaign/generate", methods=["GET"])
def campaign_generate():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  target_name = _get_req_arg_str('target')
  force_download = _get_req_arg_bool('force-download')
  images_dry_run = _get_req_arg_bool('images-dry-run')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  context.images_dry_run = images_dry_run
  validation = validate_config(context)
  if not validation['valid']:
    error = ApplicationError(
        reason=ApplicationErrorReason.INVALID_CONFIG,
        description=
        f"There errors in configuration for the selected target {target_name}: {validation['message']}"
    )
    return return_api_config_error(error)

  output_file = generate_campaign(context)
  if not output_file:
    return jsonify({
        "error": "Couldn't generate a ad campaign because no products found"
    }), 500

  zip_filename = file_utils.generate_filename(output_file, extenssion='.zip')
  # archive output csv and images, the method to do this depends on where images are
  if context.images_on_gcs and not images_dry_run:
    # images are on GCS
    gcs_output_file = context.gs_base_path + 'output/' + zip_filename
    ts_start = datetime.now()
    logging.info(f'Starting generating zip-archive on GCS')
    zs = file_utils.gcs_archive_files([context.gs_images_path],
                                      storage_client=context.storage_client,
                                      gs_path_base=context.gs_base_path)
    zs.add_path(output_file)
    with open(gcs_output_file,
              "wb",
              transport_params=dict(client=context.storage_client)) as f:
      f.writelines(zs)

    logging.info(
        f'Generated a zip-archive with campaign data on GCS: {gcs_output_file}, elapsed: {datetime.now() - ts_start}'
    )
    url = _generate_gcs_download_url(gcs_output_file, context.credentials,
                                     context.storage_client)
    arc_size = -1
  else:
    # images are local or images_dry_run=True (we won't download and zip images)
    image_folder = os.path.join(context.output_folder, context.image_folder)
    # NOTE: we need to be able to calculate zip's size, that's because not using compression
    # NOTE: we don't use standard zipfile module because it puts all files into memory while zipstream uses streaming
    zs = zipstream.ZipStream(compress_type=zipstream.ZIP_STORED, sized=True)
    zs.add_path(output_file)
    if not images_dry_run:
      zs.add_path(image_folder)

    # Should we save the zip locally as well? (for non GCP envinement)?
    #if not IS_GCP:
    # arcfilename = os.path.join(OUTPUT_FOLDER, zip_filename)
    # file_utils.zip_stream(arcfilename, [output_file, image_folder])

    arc_size = len(zs)
    if force_download or arc_size < MAX_RESPONSE_SIZE - 1024:
      # NOTE: in AppEngine maximum response size is 32MB - https://cloud.google.com/appengine/docs/standard/python3/how-requests-are-handled#response_limits
      # (and leave 1K for http stuff)
      return Response(
          zs,
          mimetype="application/zip",
          headers={
              "Content-Disposition": f"attachment; filename={zip_filename}",
              "Content-Length": len(zs),
              "Last-Modified": zs.last_modified,
          })
    else:
      # the zip-file is too big for downloading, upload it to GCS and generate a download http link for it
      gcs_output_file = context.gs_base_path + 'output/' + zip_filename
      # using smart_open streaming + zipstream we're uploading the zip to GCS
      # without loading it into memory (it can be huge)
      with open(gcs_output_file,
                "wb",
                transport_params=dict(client=context.storage_client)) as f:
        f.writelines(zs)
      logging.info(
          f'Generated zip-archive with campaign data uploaded to GCS: {gcs_output_file}'
      )
      url = _generate_gcs_download_url(gcs_output_file, context.credentials,
                                       context.storage_client)

  logging.info(f'{zip_filename} ready for download via {url}')
  return jsonify({"filename": url, "filesize": arc_size})


@app.route("/api/labels", methods=["GET"])
def get_labels():
  target_name = _get_req_arg_str('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  category_only = _get_req_arg_bool('category-only')
  product_only = _get_req_arg_bool('product-only')
  context = create_context(target_name)
  labels = context.data_gateway.load_labels(target_name,
                                            category_only=category_only,
                                            product_only=product_only)
  result = []
  for row in labels:
    obj = {}
    for col, val in row.items():
      obj[col] = val
    result.append(obj)
  return jsonify(result)


@app.route("/api/products", methods=["GET"])
def get_products():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  target_name = _get_req_arg_str('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  in_stock_only = _get_req_arg_bool('in-stock')
  long_description = _get_req_arg_bool('long-description')
  category_only = _get_req_arg_bool('category-only')
  product_only = _get_req_arg_bool('product-only')
  context = create_context(target_name)
  products = context.data_gateway.load_products(
      target_name,
      in_stock_only=in_stock_only,
      long_description=long_description,
      category_only=category_only,
      product_only=product_only)
  result = []
  for row in products:
    obj = {}
    for col, val in row.items():
      obj[col] = val
    result.append(obj)
  return jsonify(result)


@app.route("/api/products/<product_id>", methods=["POST"])
def update_product(product_id):
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  target_name = _get_req_arg_str('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  data = request.json
  context = create_context(target_name)
  context.data_gateway.update_product(target_name, product_id, data)
  return 'Updated', 200


@app.route("/api/feeds/pagefeed", methods=["GET"])
def load_pagefeed_spreadsheet():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  target_name = _get_req_arg_str('target')
  if not target_name:
    return jsonify({"error": "Required 'target' parameter is missing"}), 400
  context = create_context(target_name)
  sheets_client = sheets_utils.GoogleSpreadsheetUtils(context.credentials)
  data = sheets_client.get_values(context.target.page_feed_spreadsheetid,
                                  "A1:Z")
  return jsonify(
      data=data['values'] if 'values' in data else [],
      spreadsheet=
      f'https://docs.google.com/spreadsheets/d/{context.target.page_feed_spreadsheetid}'
  )


@app.route("/api/feeds/share", methods=["POST", "GET"])
def share_spreadsheets():
  config = _get_config()
  email = _validate_iap_jwt()
  credentials = _get_credentials()
  for target in config.targets:
    if target.page_feed_spreadsheetid:
      cloud_env_setup.set_permission_on_drive(target.page_feed_spreadsheetid,
                                              email, credentials)
    if target.adcustomizer_spreadsheetid:
      cloud_env_setup.set_permission_on_drive(target.adcustomizer_spreadsheetid,
                                              email, credentials)
  logging.info(f'All spreadsheets were shared with {email}')
  return "Ok", 200


@app.route("/api/download", methods=["GET"])
def download_file():
  filename = request.args.get('filename')
  if not filename:
    return "No file name was provided", 400
  return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


def return_api_config_error(error: ApplicationError):
  return jsonify(
      error=error.to_dict(),
      config_file=config_file_name,
  ), 500


@app.route("/api/setup/validate", methods=["GET"])
def validate_setup():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  try:
    _validate_iap_jwt()
  except:
    # It's OK if we can't detect user_email from request in non-GAE environment (no IAP)
    if IS_GAE:
      raise
  log = []
  try:
    config = _get_config()
  except FileNotFoundError:
    error = ApplicationError(
        reason=ApplicationErrorReason.NOT_INITIALIZED,
        description="Application is not initialized: config file not found")
    return return_api_config_error(error)
  credentials = _get_credentials()
  context = Context(config, None, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images'))
  log.append("Configuration file exists and readable")

  # ok, config exists, check its content
  errors = config.validate(generation=False, validate_targets=False)
  if len(errors):
    msg = "\n".join([e.error for e in errors])
    return return_api_config_error(
        ApplicationError(reason=ApplicationErrorReason.NOT_INITIALIZED,
                         description="Application is not initialized: " + msg))
  log.append("Configuratoin has no errors")

  # ok, config seems correct (at least for DT), check BQ dataset
  dataset = context.data_gateway.bq_client.get_dataset(config.dataset_id)
  if not dataset:
    return return_api_config_error(
        ApplicationError(
            reason=ApplicationErrorReason.NOT_INITIALIZED,
            description=
            f"Application is not initialized: Data Transfer dataset '{config.dataset_id}' not found)"
        ))
  log.append(f"BigQuery dataset ('{config.dataset_id}') found")

  # ok, dataset exists, check Data Transfer (existence, state, schedule)
  data_transfer = cloud_data_transfer.CloudDataTransferUtils(
      config.project_id, config.dataset_location, credentials)
  transfer_config = None
  try:
    transfer_config = data_transfer.check_merchant_center_transfer(
        config.merchant_id, config.dataset_id)
  except cloud_data_transfer.DataTransferError as e:
    app.logger.exception(e)
    return return_api_config_error(
        ApplicationError(reason=ApplicationErrorReason.NOT_INITIALIZED,
                         description=f"Application is not initialized: {e}"))
  log.append(
      f"BigQuery Data Transfer for Merchant Center ({transfer_config.name}) is valid"
  )

  # ok, DT is correct, check that config contains at least one target and that target is valid
  if len(config.targets) == 0:
    return return_api_config_error(
        ApplicationError(ApplicationErrorReason.INVALID_CONFIG,
                         f'No target found'))

  # now we'll check all targets by fetching data from our custom view (Products_Filtered_{target})
  for target in config.targets:
    try:
      context.target = target
      # NOTE: we load products here (and not labels or page_feed) because it affects both our custom tables
      products = context.data_gateway.load_products(target.name, maxrows=1)
    except Exception as e:
      app.logger.exception(e)
      return return_api_config_error(
          ApplicationError(
              ApplicationErrorReason.NOT_INITIALIZED,
              f"Application is not initialized: failed to load labels for target '{target.name}' - {e}"
          ))
  log.append(
      "Successfully fetched products from views in BigQuery for all targets")

  # finally, GCP configuration seems OK but there could be some violation/warnings in config
  try:
    response = validate_config(context)
    errors = response['errors']
  except:
    # if app wasn't initialized then validate_config will fails (it loads labels from BQ)
    errors = context.config.validate(generation=True, validate_targets=True)
  return jsonify(errors=errors, log=log)


@app.route("/api/setup/run", methods=["POST"])
def run_setup():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403

  logging.basicConfig()
  log_file_name = os.path.join(OUTPUT_FOLDER, '.setup.log')
  log_handler = logging.FileHandler(log_file_name, 'w')
  logging.root.addHandler(log_handler)

  # there are two use-cases for using this endpoint: with config arg (in body) and without
  if request.content_length > 0:
    _save_config(request.json)

  # detect current user email from IAP token in http headers
  user_email = ''
  try:
    user_email = _validate_iap_jwt()
  except:
    # It's OK if we can't detect user_email from request in non-GAE environment (no IAP)
    if IS_GAE:
      raise

  try:
    g_setup_lock.acquire()
    skip_dt_run = request.args.get('skip-dt-run') == 'true' or False
    skip_spreadsheets = request.args.get('skip-spreadsheets') == 'true' or False
    try:
      config = _get_config()
    except FileNotFoundError:
      error = ApplicationError(
          reason=ApplicationErrorReason.NOT_INITIALIZED,
          description=
          "Application is not initialized: config file not found, please fill in configuration settings and save"
      )
      return return_api_config_error(error)
    credentials = _get_credentials()
    logging.info(
        f'Ready to run deployment (user_email: {user_email}, skip_dt_run: {skip_dt_run})'
    )
    # TODO: check SA's permissions
    # TODO: before running a new deployment we might check for existing components and remove them
    created = cloud_env_setup.deploy(
        config, credentials,
        cloud_env_setup.DeployOptions(skip_dt_run, user_email,
                                      skip_spreadsheets))

    if created:
      # overwrite config file with new data
      config_utils.save_config(config, config_file_name)
      if config_file_name and config_file_name.startswith("gs://"):
        if (args.config != config_file_name):
          # update local cache
          config_utils.save_config(config, args.config)

    # fetch labels for category mapping (they need a label-description mapping)
    context = Context(config, None, credentials,
                      ContextOptions(OUTPUT_FOLDER, 'images'))
    labels_by_target = {}
    for target in config.targets:
      try:
        context.target = target
        category_labels = context.data_gateway.load_labels(target.name, category_only=True)
        if category_labels.total_rows:
          labels = []
          for row in category_labels:
            labels.append(row[0])
          labels_by_target[target.name] = labels
      except BaseException as e:
        app.logger.exception(e)
        msg = f'Setup was successful but reading of labels failed: {e}'
        return return_api_config_error(
            ApplicationError(reason=ApplicationErrorReason.INVALID_DEPLOYMENT,
                             description=msg))

    logging.info('Fetched labels for all targets')
    log = ''
    log_handler.close()
    logging.root.removeHandler(log_handler)
    log_handler = None
    with open(log_file_name, 'r') as f:
      log = f.readlines()
    return jsonify(log=log, labels=labels_by_target)
  except BaseException as e:
    app.logger.exception(e)
    msg = str(e)
    if type(e) is cloud_data_transfer.DataTransferError:
      msg = f"GMC Data Transfer failed: {e}"
    return return_api_config_error(
        ApplicationError(reason=ApplicationErrorReason.INVALID_CLOUD_SETUP,
                         description=msg))
  finally:
    g_setup_lock.release()
    if log_handler:
      log_handler.close()
      logging.root.removeHandler(log_handler)


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
      error = ApplicationError(
          reason=ApplicationErrorReason.INVALID_DEPLOYMENT,
          description=
          "The application uses a local config file and it does not exist")
    else:
      error = ApplicationError(
          reason=ApplicationErrorReason.NOT_INITIALIZED,
          description="Application is not initialized: config file not found")
    return return_api_config_error(error)

  credentials = _get_credentials()
  context = Context(config, None, credentials,
                    ContextOptions(OUTPUT_FOLDER, 'images'))

  # ok, config exists, check its validity
  errors = context.config.validate(generation=True, validate_targets=True)
  # TODO: not sure how deep the validation should be (validate_config vs config.validate)
  # try:
  #   response = validate_config(context)
  #   errors = response['errors']
  # except:
  #   # if app wasn't initialized then validate_config will fails (it loads labels from BQ)
  #   errors = context.config.validate(generation=True, validate_targets=True)

  # TODO commit_link = 'https://github.com/google/product-dsa/commit/' + os.environ.get('GIT_COMMIT')
  commit = os.getenv('GIT_COMMIT') or ''
  if commit:
    commit = 'https://professional-services.googlesource.com/solutions/product-dsa/+/' + commit

  return jsonify(config=config.to_dict(),
                 config_file=config_file_name,
                 commit_link=commit,
                 errors=errors)


def _save_config(config):
  content = json.dumps(config, indent=2)
  # we can update config if and only if it's stored on GCS (i.e. args.config has a gcs url)
  if config_file_name and config_file_name.startswith("gs://"):
    file_utils.save_file_to_gcs(config_file_name, content)
    # and update the local cache in /tmp
    if (args.config == config_file_name):
      # this means that the config wasn't copied to /tmp on start (because it didn't exist)
      copy_config_to_cache(config_file_name)
    else:
      # update local cache
      file_utils.save_file_content(args.config, content)
  elif not IS_GAE:
    # local file and local server, just save it
    file_utils.save_file_content(config_file_name, content)
  else:
    # GAE but config isn't on GCS (a local file inside container)
    msg = f'Updating config is not possible because it is not stored on GCS. Please make sure your app.yaml has CONFIG env var with an external writable path to config file (GCS)'
    logging.warning(msg)
    raise Exception(msg)


@app.route("/api/config", methods=["POST"])
def post_config():
  if g_setup_lock.is_locked():
    return jsonify({"error": "Operation is forbidden as setup is executing"
                   }), 403
                   
  new_config = request.get_json(cache=False)
  _save_config(new_config)

  config = _get_config()
  errors = config.validate(generation=True, validate_targets=True)
  return jsonify(errors=errors)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
  # NOTE: we don't use Flusk standard support for static files
  # (static_folder option and send_static_file method)
  # because they can't distinguish requests for static files (js/css) and client routes (like /products)
  file_requested = os.path.join(app.root_path, STATIC_DIR, path)
  if not os.path.isfile(file_requested):
    path = "index.html"
  max_age = 0 if path == "index.html" else None
  response = send_from_directory(STATIC_DIR, path, max_age=max_age)
  # There is a "feature" in GAE - all files have zeroed timestamp ("Tue, 01 Jan 1980 00:00:01 GMT")
  if IS_GAE:
    response.headers.remove("Last-Modified")
  response.cache_control.no_store = True

  return response


@app.errorhandler(Exception)
def handle_exception(e: Exception):
  app.logger.exception(e)
  if request.content_type == "application/json" and request.path.startswith(
      '/api/'):
    # NOTE: not all exceptions can be serialized
    try:
      return jsonify({"error": e}), 500
    except:
      return jsonify({"error": str(e)}), 500
  return e


@app.route("/_ah/start")
def on_instance_start():
  """Instance start handler. It's called by GAE to start a new instance (not workers).

  Be mindful about code here because errors won't be propagated to webapp users
  (i.e. visible only in log)"""
  # copy config from GCS to local cache
  if config_on_gcs:
    # config is on GCS, copy it from GCS to local cache
    copy_config_to_cache(config_file_name)

  # activate GCP diagnostics services if needed (actually they can be used even outside GAE)
  if IS_GAE and os.getenv('CLOUD_PROFILER', '').upper() == 'TRUE':
    try:
      import googlecloudprofiler
      googlecloudprofiler.start(verbose=3)
    except (ValueError, NotImplementedError) as exc:
      logging.exception(exc)
  if IS_GAE and os.getenv('CLOUD_DEBUGGER', '').upper() == 'TRUE':
    try:
      import googleclouddebugger
      googleclouddebugger.enable()
    except ImportError:
      # NOTE: this googleclouddebugger can be installed ONLY on Linux
      pass
  return 'OK', 200


if not IS_GAE:
  on_instance_start()

# construct expected_audience field that we need for validation IAP JWT headers, it not works in GAE
if IS_GAE:
  credentials = _get_credentials()
  project_id = config_utils.find_project_id(args)
  rmclient = ProjectsClient(credentials=credentials)
  # fetch project number via Cloud ResourceManager (yes, project.name is project number)
  project = rmclient.get_project(name=f'projects/{project_id}')
  expected_audience = f'/{project.name}/apps/{project_id}'
  logging.info(f'Detected IAP audience: {expected_audience}')


if __name__ == '__main__':
  # NOTE: we run server.py directly only during development, normally it's run by gunicorn in GAE
  parser = argparse.ArgumentParser()
  parser.add_argument('--debug', action='store_true')
  parser.add_argument('--log-level',
                      dest='log_level',
                      help='Logging level: DEBUG, INFO, WARN, ERROR')
  srv_args = parser.parse_known_args()[0]
  if srv_args.log_level:
    logging.getLogger().setLevel(srv_args.log_level)
  app.run(debug=srv_args.debug)  # run our Flask app
