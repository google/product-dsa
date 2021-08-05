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

# python3
"""Cloud BigQuery module."""

import logging
import os
from typing import Any, Dict, Union, Sequence
from google.auth import credentials
from google.cloud import bigquery
from google.cloud import exceptions

# Main workflow sql.
_MAIN_WORKFLOW_SQL = 'scripts/main_workflow.sql'

# Set logging level.
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)


class CloudBigQueryUtils(object):
  """This class provides methods to simplify BigQuery API usage."""

  def __init__(self, project_id: str, credentials: credentials.Credentials):
    """Initialise new instance of CloudDataTransferUtils.

    Args:
      project_id: GCP project id.
    """
    self.project_id = project_id
    self.client = bigquery.Client(project=project_id, credentials=credentials)

  def create_dataset_if_not_exists(self, dataset_id: str, dataset_location: str) -> None:
    """Creates BigQuery dataset if it doesn't exists.

    Args:
      project_id: A cloud project id.
      dataset_id: BigQuery dataset id.
    """
    # Construct a BigQuery client object.
    fully_qualified_dataset_id = f'{self.project_id}.{dataset_id}'
    try:
      self.client.get_dataset(fully_qualified_dataset_id)
      logging.info('Dataset %s already exists.', fully_qualified_dataset_id)
    except exceptions.NotFound:
      logging.info('Dataset %s is not found.', fully_qualified_dataset_id)
      dataset = bigquery.Dataset(fully_qualified_dataset_id)
      dataset.location = dataset_location
      self.client.create_dataset(dataset)
      logging.info('Dataset %s created.', fully_qualified_dataset_id)

  def read_file(self, file_path: str) -> str:
    """Reads and returns contents of the file.

    Args:
      file_path: File path.

    Returns:
      content: File content.

    Raises:
        FileNotFoundError: If the provided file is not found.
    """
    try:
      with open(file_path, 'r') as stream:
        content = stream.read()
    except FileNotFoundError:
      raise FileNotFoundError(
        f'The file "{file_path}" could not be found.')
    else:
      return content

  def configure_sql(self, sql_path: str, query_params: Dict[str, Any]) -> str:
    """Configures parameters of SQL script with variables supplied.

    Args:
      sql_path: Path to SQL script.
      query_params: Configuration containing query parameter values.

    Returns:
      sql_script: String representation of SQL script with parameters assigned.
    """
    sql_script = self.read_file(sql_path)

    params = {}
    for param_key, param_value in query_params.items():
      # If given value is list of strings (ex. 'a,b,c'), create tuple of
      # strings (ex. ('a', 'b', 'c')) to pass to SQL IN operator.
      if isinstance(param_value, str) and ',' in param_value:
        params[param_key] = tuple(param_value.split(','))
      else:
        params[param_key] = param_value

    return sql_script.format(**params)

  def execute_queries(self, sql_files: Sequence[str], dataset_id: str, dataset_location: str, merchant_id: str, customer_id: str) -> None:
    """Executes list of queries."""

    prefix = 'scripts'
    query_params = {
      'project_id': self.project_id,
      'dataset': dataset_id,
      'merchant_id': merchant_id,
      'external_customer_id': customer_id
    }

    for sql_file in sql_files:
      try:
        query = self.configure_sql(
            os.path.join(prefix, sql_file), 
            query_params)
        query_job = self.client.query(query, location=dataset_location)
        query_job.result()
      except:
        logging.exception('Error in %s', sql_file)
        raise

  def get_main_workflow_sql(self, dataset_id: str, merchant_id: str,
                            customer_id: str) -> str:
    """Returns main workflow sql.

    Args:
      project_id: A cloud project id.
      dataset_id: BigQuery dataset id.
      merchant_id: Merchant center id.
      customer_id: Google Ads customer id.
    """
    query_params = {
      'project_id': self.project_id,
      'dataset': dataset_id,
      'merchant_id': merchant_id,
      'external_customer_id': customer_id
    }
    return self.configure_sql(_MAIN_WORKFLOW_SQL, query_params)
