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
"""Cloud BigQuery module."""

import logging
import os
import re
from typing import Any, Dict, List, Union, Sequence
from google.auth import credentials
from google.cloud import bigquery
from google.api_core import exceptions
from google.cloud.bigquery.dataset import Dataset
from common import file_utils

# Set logging level.
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)


class CloudBigQueryUtils(object):
  """This class provides methods to simplify BigQuery API usage."""

  def __init__(self, project_id: str, credentials: credentials.Credentials,
               dataset_location: str = ''):
    """Initialise new instance of CloudBigQueryUtils.

    Args:
      project_id: GCP project id.
      credentials: google.auth credentials
    """
    self.project_id = project_id
    self.client = bigquery.Client(project=project_id,
                                  credentials=credentials,
                                  location=dataset_location)

  def create_dataset_if_not_exists(self, dataset_id: str,
                                   dataset_location: str) -> None:
    """Creates BigQuery dataset if it doesn't exists.

    Args:
      project_id: A cloud project id.
      dataset_id: BigQuery dataset id.
    """
    # Construct a BigQuery client object.
    fully_qualified_dataset_id = f'{self.project_id}.{dataset_id}'
    to_create = False
    try:
      ds = self.client.get_dataset(fully_qualified_dataset_id)
      if ds.location and dataset_location and ds.location.lower() != dataset_location.lower() or \
         not ds.location and dataset_location or \
         ds.location and not dataset_location:
        self.client.delete_dataset(fully_qualified_dataset_id, True)
        logging.info(
            'Existing dataset needs to be recreated due to different location')
        to_create = True
      else:
        logging.info('Dataset %s already exists.', fully_qualified_dataset_id)
    except exceptions.NotFound:
      logging.info('Dataset %s is not found.', fully_qualified_dataset_id)
      to_create = True
    if to_create:
      dataset = bigquery.Dataset(fully_qualified_dataset_id)
      dataset.location = dataset_location
      self.client.create_dataset(dataset)
      logging.info('Dataset %s created.', fully_qualified_dataset_id)

  def get_dataset(self, dataset_id: str) -> Dataset:
    fully_qualified_dataset_id = f'{self.project_id}.{dataset_id}'
    try:
      return self.client.get_dataset(fully_qualified_dataset_id)
    except exceptions.NotFound:
      pass

  def _configure_sql(self, sql_script: str, query_params: Dict[str,
                                                               Any]) -> str:
    """Configures parameters of SQL script with variables supplied.

    Args:
      sql_script: SQL script.
      query_params: Configuration containing query parameter values.

    Returns:
      sql_script: String representation of SQL script with parameters assigned.
    """
    params = {}
    for param_key, param_value in query_params.items():
      # If given value is list of strings (ex. 'a,b,c'), create tuple of
      # strings (ex. ('a', 'b', 'c')) to pass to SQL IN operator.
      if isinstance(param_value, str) and ',' in param_value:
        params[param_key] = tuple(param_value.split(','))
      if isinstance(param_value, list):
        params[param_key] = tuple(param_value)
      else:
        params[param_key] = param_value

    return sql_script.format(**params)

  def _get_query_params(self, dataset_id: str, params: Dict[str, Any]):
    query_params = {
        'project_id': self.project_id,
        'dataset': dataset_id,
        'dataset_fqn': f'{self.project_id}.{dataset_id}'
    }
    query_params = {**query_params, **params}
    return query_params

  def execute_scripts(self,
                      sql_files: Union[Sequence[str], str],
                      dataset_id: str,
                      params: Dict[str, Any],
                      sql_params: List[bigquery.ScalarQueryParameter] = None):
    """Executes a SQL query script or a list of scripts."""
    if isinstance(sql_files, str):
      sql_files = [sql_files]
    query_params = self._get_query_params(dataset_id, params)
    for idx, sql_file in enumerate(sql_files):
      try:
        sql_path = os.path.join('sql', sql_file)
        sql_script = file_utils.get_file_content(sql_path)
        query = self._configure_sql(sql_script, query_params)
        job_config = None
        if sql_params:
          job_config = bigquery.QueryJobConfig(query_parameters=sql_params)
        query_job = self.client.query(query, job_config=job_config)
        if idx == len(sql_files) - 1:
          # TODO: theriotically we can combine several results together if needed
          return query_job.result()
        query_job.result()
      except Exception as e:
        logging.exception(
            f'Error occurred during \'{sql_file}\' script execution: {e}')
        if (isinstance(e, exceptions.NotFound)):
          match = re.match('Not found: (Table|View) ([^ ]+) was not found',
                           e.message)
          if match and match.groups:
            # Example: "Not found: Table project:gmcdsa.Ads_Preview_Products_Target was not found in location US"
            raise Exception(
                f'{match.group(1)} \'{match.group(2)}\' doesn\'t exist, you should run setup again'
            )
        raise

  def execute_query(self,
                    sql_query: str,
                    dataset_id: str,
                    params: Dict[str, Any],
                    sql_params: List[bigquery.ScalarQueryParameter] = None):
    query_params = self._get_query_params(dataset_id, params)
    try:
      query = self._configure_sql(sql_query, query_params)
      job_config = None
      if sql_params:
        job_config = bigquery.QueryJobConfig(query_parameters=sql_params)
      query_job = self.client.query(query, job_config=job_config)
      return query_job.result()
    except Exception as e:
      logging.exception(f'Error occurred during script execution: {e}')
      raise