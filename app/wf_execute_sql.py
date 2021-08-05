# Lint as: python3
"""A workflow implementation for app.py. Run arbitrary sql from a file or files.

Support reading sql files locally or from GCS.
"""

import time
import datetime
from google.cloud import bigquery
import cloud_utils

def run(cfg, context):
  # either sql_file or sql_fiels can be used, but not together
  wf = ExecuteSqlWorkflow(
    project_id = cfg['project_id'],
    sql_file = cfg.get('sql_file'),
    sql_files = cfg.get('sql_files'),
    macros = cfg.get('macros')
    )
  wf.run(context)


class ExecuteSqlWorkflow:

  def __init__(self, project_id, sql_file, sql_files, macros):
    self.project_id = project_id
    if sql_file:
      self.sql_templates = [cloud_utils.get_file_content(sql_file)]
    elif sql_files:
      self.sql_templates = [cloud_utils.get_file_content(s) for s in sql_files]
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
    #print(sql)
    bq_client = bigquery.Client()
    # see https://cloud.google.com/bigquery/docs/reference/rest/v2/Job#jobconfigurationquery
    #job_config = bigquery.QueryJobConfig(destination='', write_disposition='WRITE_TRUNCATE')
    print(sql)
    query_job = bq_client.query(sql)
    res = query_job.result()
    print(res)

  def run(self, context):
    for tmpl in self.sql_templates:
        self._execute_query(tmpl, context)
