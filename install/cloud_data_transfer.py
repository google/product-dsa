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

# python3
"""Module for managing BigQuery data transfers."""

from common.config_utils import ApplicationError, ApplicationErrorReason
import datetime
import logging
import time
from typing import Any, Dict, List, Iterable

import pytz
from google.auth import credentials
import google.protobuf.json_format
from google.cloud import bigquery_datatransfer_v1
from google.cloud.bigquery_datatransfer_v1 import types
from google.protobuf import struct_pb2, timestamp_pb2
from google.api_core import exceptions


_MERCHANT_CENTER_ID = 'merchant_center'  # Data source id for Merchant Center.
_GOOGLE_ADS_ID = 'adwords'  # Data source id for Google Ads.
_SLEEP_SECONDS = 5  # Seconds to sleep before checking resource status.
_MAX_WAIT_SECONDS = 1200  # Maximum seconds to wait for an operation to complete (20 minutes)


class DataTransferError(Exception):
  """An exception to be raised when data transfer was not successful."""


class CloudDataTransferUtils(object):
  """This class provides methods to manage BigQuery data transfers.

    Typical usage example:
      >>> data_transfer = CloudDataTransferUtils('project_id')
      >>> data_transfer.create_merchant_center_transfer(12345, 'dataset_id')
  """

  def __init__(self, project_id: str, dataset_location: str,
               credentials: credentials.Credentials):
    """Initialise new instance of CloudDataTransferUtils.

    Args:
      project_id: GCP project id.
    """
    self.project_id = project_id
    self.dataset_location = dataset_location
    self.client = bigquery_datatransfer_v1.DataTransferServiceClient(
        credentials=credentials)

  def _list_transfer_configs_with_retry(self, parent: str) -> Iterable[types.TransferConfig]:
    run = 1
    MAX_TRY = 10
    while True:
      try:
        return self.client.list_transfer_configs(parent=parent)
      except exceptions.NotFound as e:
        if run > MAX_TRY:
          raise
        run += 1
        logging.warning(
            f'list_transfer_configs failed with {str(e)}, repeating ({run})')

  def _get_existing_transfer(self,
                             data_source_id: str,
                             destination_dataset_id: str = None,
                             params: Dict[str, str] = None,
                             name: str = None) -> types.TransferConfig:
    """Gets data transfer if it already exists.

    Args:
      data_source_id: Data source id for GMC Data Transfer.
      destination_dataset_id: BigQuery dataset id.
      params: Data transfer specific parameters.

    Returns:
      Data Transfer if the transfer already exists.
      None otherwise.
    """
    parent = f'projects/{self.project_id}'  #/locations/{self.dataset_location}'
    logging.info(f'Checking for existing BQ Data Transfer in {parent}')
    for transfer_config in self._list_transfer_configs_with_retry(
        parent=parent):
      if transfer_config.data_source_id != data_source_id:
        continue
      if destination_dataset_id and transfer_config.destination_dataset_id != destination_dataset_id:
        continue
      # If the transfer config is in Failed state, we should ignore.
      is_valid_state = transfer_config.state in (types.TransferState.PENDING,
                                                 types.TransferState.RUNNING,
                                                 types.TransferState.SUCCEEDED)
      params_match = self._check_params_match(transfer_config, params)
      name_matches = name is None or name == transfer_config.display_name
      # TODO: transfer_config.userId contains a userid for a user under which the transfer running
      #       we could campare it with the current user from credentials. But how?
      if params_match and is_valid_state and name_matches:
        # we found an existing transfer but it's in a wrong location so we have to delete it
        if self.dataset_location and transfer_config.dataset_region and self.dataset_location != transfer_config.dataset_region:
          logging.info(
              f"Found a suitable BQ Data Transfer {transfer_config.name} but it's in '{transfer_config.dataset_region}' location while expected '{self.dataset_location}', deleting"
          )
          self.client.delete_transfer_config(name=transfer_config.name)
          return None

        return transfer_config
    return None

  def _check_params_match(self, transfer_config: types.TransferConfig,
                          params: Dict[str, str]) -> bool:
    """Checks if given parameters are present in transfer config.

    Args:
      transfer_config: Data transfer configuration.
      params: Data transfer specific parameters.

    Returns:
      True if given parameters are present in transfer config, False otherwise.
    """
    if not params:
      return True
    for key, value in params.items():
      config_params = transfer_config.params
      if key not in config_params or config_params[key] != value:
        return False
    return True

  def _update_existing_transfer(self, transfer_config: types.TransferConfig,
                                params: Dict[str, str], dt_schedule: str,
                                pubsub_topic: str) -> types.TransferConfig:
    """Updates existing data transfer.

    If the parameters are already present in the config, then the transfer
    config update is skipped.

    Args:
      transfer_config: Data transfer configuration to update.
      params: Data transfer specific parameters.

    Returns:
      Updated data transfer config.
    """
    if self._check_params_match(
        transfer_config, params
    ) and transfer_config.schedule == dt_schedule and transfer_config.schedule_options.disable_auto_scheduling == False and transfer_config.notification_pubsub_topic == pubsub_topic:
      logging.info(
          'The data transfer config "%s" parameters match. '
          'Hence skipping update.', transfer_config.display_name)
      # NOTE: if other parameters mismatch we won't catch this
      return transfer_config
    new_transfer_config = types.TransferConfig()
    types.TransferConfig.copy_from(new_transfer_config, transfer_config)
    # Clear existing parameter values.
    new_transfer_config.params = struct_pb2.Struct()
    for key, value in params.items():
      new_transfer_config.params[key] = value
    if transfer_config.schedule == '':
      new_transfer_config.schedule = dt_schedule
      schedule_options = types.ScheduleOptions()
      schedule_options.disable_auto_scheduling = False
      new_transfer_config.schedule_options = schedule_options
    new_transfer_config.notification_pubsub_topic = pubsub_topic
    # Only params field is updated.
    update_mask = {
        "paths": [
            "params", "schedule", "schedule_options",
            "notification_pubsub_topic"
        ]
    }
    new_transfer_config = self.client.update_transfer_config(
        transfer_config=new_transfer_config, update_mask=update_mask)
    logging.info('The data transfer config "%s" parameters updated.',
                 new_transfer_config.display_name)
    return new_transfer_config

  def _get_transfer_run_errors(self, transfer_run: types.TransferRun) -> List[str]:
    try:
      response = self.client.list_transfer_logs(
          types.ListTransferLogsRequest(
              parent=transfer_run.name,
              message_types=[types.TransferMessage.MessageSeverity.ERROR]))
      errors = []
      for log_ in response:  # log_ is types.TransferMessage
        errors.append(log_.message_text)
      return errors
    except exceptions.GoogleAPICallError as e:
      logging.exception(e)
      return [str(transfer_run.error_status)]

  def _get_transfer_last_run_errors(self,
                                    transfer_config: types.TransferConfig) -> List[str]:
    latest_run: types.TransferRun = self._get_transfer_last_run(transfer_config)
    if not latest_run:
      return []
    return self._get_transfer_run_errors(latest_run)

  def _get_transfer_last_run(self, transfer_config: types.TransferConfig) -> types.TransferRun:
    response = self.client.list_transfer_runs(parent=transfer_config.name)
    latest_run: types.TransferRun = None
    for run_ in response:
      latest_run = run_
      break
    return latest_run

  def check_merchant_center_transfer(
      self, merchant_id: int, destination_dataset: str) -> types.TransferConfig:
    parameters = self._create_transfer_params(merchant_id)
    parent = f'projects/{self.project_id}'  #/locations/{self.dataset_location}'
    transfer_config_: types.TransferConfig = None
    transfer_config: types.TransferConfig = None
    for transfer_config_ in self.client.list_transfer_configs(parent=parent):
      if transfer_config_.data_source_id != _MERCHANT_CENTER_ID:
        continue
      if destination_dataset and transfer_config_.destination_dataset_id != destination_dataset:
        continue
      params_match = self._check_params_match(transfer_config_, parameters)
      if not params_match:
        continue
      # this is a DT for GMC, targets our dataset, and our merchant_id
      if transfer_config_.state == types.TransferState.FAILED:
        errors = self._get_transfer_last_run_errors(transfer_config_)
        error_msg = '\n'.join(errors)
        # "No Products data to transfer found for your Google Merchant Center account"
        raise DataTransferError(
            f'Data Transfer ({transfer_config_.display_name}) for GMC account {merchant_id} is in FAILED state, last run result: {error_msg}'
        )
      transfer_config = transfer_config_
      break
    if not transfer_config:
      raise DataTransferError(
          f'Data Transfer for GMC account {merchant_id} not found')
    return transfer_config

  def _create_transfer_params(self, merchant_id: str):
    parameters = struct_pb2.Struct()
    parameters['merchant_id'] = str(
        merchant_id
    )  # w/o str the value will be converted to float and cause an API error
    parameters['export_products'] = True
    # "export_regional_inventories":"true",
    # "export_local_inventories":"true",
    # "export_price_benchmarks":"true",
    # "export_best_sellers":"true"
    return parameters

  def create_merchant_center_transfer(
      self, merchant_id: int, destination_dataset: str, dt_schedule: str,
      pubsub_topic: str, skip_dt_run: bool) -> types.TransferConfig:
    """Creates a new merchant center transfer.

    Merchant center allows retailers to store product info into Google. This
    method creates a data transfer config to copy the product data to BigQuery.

    Args:
      merchant_id: Google Merchant Center(GMC) account id.
      destination_dataset: BigQuery dataset id.
      pubsub_topic: Pub/Sub topic id to publish message on DT completion

    Returns:
      Transfer config.
    """
    logging.info('Creating Merchant Center Transfer.')
    parameters = self._create_transfer_params(merchant_id)

    data_transfer_config = self._get_existing_transfer(_MERCHANT_CENTER_ID,
                                                       destination_dataset,
                                                       parameters)
    if data_transfer_config:
      # though a DT exists it might neeed to be updated for applying schedule, pubsub, params
      logging.info(
          f"Found an existing data transfer for merchant id {merchant_id} and dataset '{destination_dataset}' ({data_transfer_config.name})"
      )
      data_transfer_config = self._update_existing_transfer(
          data_transfer_config, parameters, dt_schedule, pubsub_topic)
      # trigger execution start_manual_transfer_runs
      if not skip_dt_run:
        logging.info(f'Triggering data transfer to run...')
        run_time = datetime.datetime.now(tz=pytz.utc)
        run_time_pb = timestamp_pb2.Timestamp()
        run_time_pb.FromDatetime(run_time)
        transfer_run = self.client.start_manual_transfer_runs(
            types.StartManualTransferRunsRequest(
                parent=data_transfer_config.name,
                requested_run_time=run_time_pb)).runs
        logging.info(f'Data transfer has been run')
      else:
        logging.info(
            'Skipping data transfer running because of skip-dt-run flag')
      return data_transfer_config

    transfer_config_input = {
        'display_name': f'Merchant Center Transfer - {merchant_id}',
        'data_source_id': _MERCHANT_CENTER_ID,
        'destination_dataset_id': destination_dataset,
        'schedule': dt_schedule,
        'params': parameters,
        'data_refresh_window_days': 0,
        'notification_pubsub_topic': pubsub_topic
    }
    parent = f'projects/{self.project_id}'  #/locations/{self.dataset_location}'
    logging.info(
        f'Creating BQ Data Transfer in {parent} for merchant id {merchant_id} to destination dataset {destination_dataset}'
    )
    # NOTE: DT will run on creation, we can't suppress running (if skip_dt_run=True)
    transfer_config = self.client.create_transfer_config(
        parent=parent, transfer_config=transfer_config_input)
    logging.info(
        f'Data transfer created for merchant id {merchant_id} to destination dataset {destination_dataset}'
    )
    return transfer_config

  def create_google_ads_transfer(
      self,
      customer_id: str,
      destination_dataset: str,
      backfill_days: int = 30) -> types.TransferConfig:
    """Creates a new Google Ads transfer.

    This method creates a data transfer config to copy Google Ads data to
    BigQuery dataset.

    Args:
      customer_id: Google Ads customer id.
      destination_dataset: BigQuery dataset id.
      backfill_days: Number of days to backfill.

    Returns:
      Transfer config.
    """
    logging.info('Creating Google Ads Transfer.')

    parameters = struct_pb2.Struct()
    parameters['customer_id'] = customer_id
    data_transfer_config = self._get_existing_transfer(_GOOGLE_ADS_ID,
                                                       destination_dataset,
                                                       parameters)
    if data_transfer_config:
      logging.info(
          'Data transfer for Google Ads customer id %s to destination dataset '
          '%s already exists.', customer_id, destination_dataset)
      return data_transfer_config
    logging.info(
        'Creating data transfer for Google Ads customer id %s to destination '
        'dataset %s', customer_id, destination_dataset)

    parent = f'projects/{self.project_id}/locations/{self.dataset_location}'
    transfer_config_input = {
        'display_name': f'Google Ads Transfer - {customer_id}',
        'data_source_id': _GOOGLE_ADS_ID,
        'destination_dataset_id': destination_dataset,
        'params': parameters,
        'data_refresh_window_days': 1,
    }
    request = types.CreateTransferConfigRequest()
    request.parent = parent
    request.transfer_config = transfer_config_input
    transfer_config = self.client.create_transfer_config(request=request)
    logging.info(
        'Data transfer created for Google Ads customer id %s to destination '
        'dataset %s', customer_id, destination_dataset)
    if backfill_days:
      transfer_config_name = transfer_config.name
      transfer_config_id = transfer_config_name.split('/')[-1]
      start_time = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(
          days=backfill_days)
      end_time = datetime.datetime.now(tz=pytz.utc)
      start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
      end_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
      # parent = self.client.location_transfer_config_path(self.project_id, dataset_location, transfer_config_id)
      parent = f'projects/{self.project_id}/locations/{self.dataset_location}/transferConfigs/{transfer_config_id}'
      start_time_pb = timestamp_pb2.Timestamp()
      end_time_pb = timestamp_pb2.Timestamp()
      start_time_pb.FromDatetime(start_time)
      end_time_pb.FromDatetime(end_time)
      self.client.schedule_transfer_runs(parent=parent,
                                         start_time=start_time_pb,
                                         end_time=end_time_pb)
    return transfer_config

  def schedule_query(self, name: str,
                     query_string: str) -> types.TransferConfig:
    """Schedules query to run every day.
       NOTE: currently not used, To Be Deleted

    Args:
      name: Name of the scheduled query.
      query_string: The query to be run.
    """
    data_transfer_config = self._get_existing_transfer('scheduled_query',
                                                       name=name)
    parameters = struct_pb2.Struct()
    parameters['query'] = query_string
    if data_transfer_config:
      logging.info('Data transfer for scheduling query "%s" already exists.',
                   name)
      return self._update_existing_transfer(data_transfer_config, parameters)
    parent = f'projects/{self.project_id}/locations/{self.dataset_location}'
    params = {
        'query': query_string,
    }
    transfer_config_input = google.protobuf.json_format.ParseDict(
        {
            'display_name': name,
            'data_source_id': 'scheduled_query',
            'params': params,
            'schedule': 'every 24 hours',
        },
        bigquery_datatransfer_v1.types.TransferConfig()._pb,
    )
    request = types.CreateTransferConfigRequest()
    request.parent = parent
    request.transfer_config = transfer_config_input
    transfer_config = self.client.create_transfer_config(request=request)
    return transfer_config

  def wait_for_transfer_started(self, transfer_config: types.TransferConfig):
    self._wait_for_transfer_status(transfer_config, types.TransferState.RUNNING)

  def wait_for_transfer_completion(self, transfer_config: types.TransferConfig):
    self._wait_for_transfer_status(transfer_config,
                                   types.TransferState.SUCCEEDED)

  def _wait_for_transfer_status(self, transfer_config: types.TransferConfig,
                                state: types.TransferState):
    """Waits for the completion of data transfer operation.

    This method retrieves data transfer operation and checks for its status. If
    the operation is not completed, then the operation is re-checked after
    `_SLEEP_SECONDS` seconds.

    Args:
      transfer_config: Resource representing data transfer.

    Raises:
      DataTransferError: If the data transfer is not successfully completed.
    """
    transfer_config_name = transfer_config.name
    started = time.time()
    while True:
      latest_transfer = self._get_transfer_last_run(transfer_config)
      if not latest_transfer:
        return
      if (latest_transfer.state == state):
        return
      if latest_transfer.state == types.TransferState.SUCCEEDED:
        logging.info('Transfer %s was successful.', transfer_config_name)
        return
      if (latest_transfer.state == types.TransferState.FAILED or
          latest_transfer.state == types.TransferState.CANCELLED):
        errors = self._get_transfer_run_errors(latest_transfer)
        error_message = (
            f'Transfer {transfer_config_name} was not successful: '
            '\n'.join(errors))
        logging.error(error_message)
        raise DataTransferError(error_message)
      logging.info(
          f'Transfer {transfer_config_name} still in progress. Sleeping for {_SLEEP_SECONDS} seconds before checking again.'
      )
      time.sleep(_SLEEP_SECONDS)
      elapsed = time.time() - started
      if elapsed > _MAX_WAIT_SECONDS:
        error_message = f'Transfer {transfer_config_name} is taking too long to finish. Hence failing the request.'
        logging.error(error_message)
        raise DataTransferError(error_message)
