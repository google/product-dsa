# Lint as: python3
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
"""Run arbitrary SQL script in BigQuery, supporting reading their content from file/files or GCSE.
"""

import time
import datetime
from google.auth import credentials
from google.cloud import bigquery
from common import file_utils

def run(cfg, context):
  # either sql_file or sql_fiels can be used, but not together
  wf = ExecuteSqlWorkflow(
    project_id = cfg.get('project_id'),
    sql_file = cfg.get('sql_file'),
    sql_files = cfg.get('sql_files'),
    macros = cfg.get('macros')
    )
  return wf.run(context)


class ExecuteSqlWorkflow:

  def __init__(self, project_id, sql_file, sql_files, macros):
    self.project_id = project_id
    if sql_file:
      self.sql_templates = [file_utils.get_file_content(sql_file)]
    elif sql_files:
      self.sql_templates = [file_utils.get_file_content(s) for s in sql_files]
    else:
      raise Exception('Either sql_file or sql_files argument should be specified')
    if macros:
      self.macros = {**macros}
    else:
      self.macros = {}

  def _substitute_macros(self, sql_template, context):
    macros = self.macros
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    macros["TODAY"] = yesterday.strftime('%Y%m%d')
    xcom = context['xcom']
    if xcom:
      macros = {**macros, **xcom}
    sql = sql_template.format(**macros)
    return sql

  def _execute_query(self, sql_template, context):
    sql = self._substitute_macros(sql_template, context)
    #ts = time.strftime('%d %b %Y %H:%M:%S %z')
    #print(f'{ts}: Executing a query: ')
    bq_client = bigquery.Client(project=self.project_id, credentials=context['gcp_credentials'])
    # see https://cloud.google.com/bigquery/docs/reference/rest/v2/Job#jobconfigurationquery
    #job_config = bigquery.QueryJobConfig(destination='', write_disposition='WRITE_TRUNCATE')
    #print(sql)
    query_job = bq_client.query(sql)
    res = query_job.result()
    return res

  def run(self, context):
    for tmpl in self.sql_templates:
      result = self._execute_query(tmpl, context)
    return result
