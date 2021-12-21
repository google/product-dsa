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
from typing import Dict, List
from google.auth import credentials
from google.cloud import bigquery
from common import config_utils, bigquery_utils
import logging


class DataGateway:
  """Object for loading and udpating data in Database
  (which is BigQuery but it should be hidden from consumers)"""

  def __init__(self, config: config_utils.Config,
               credentials: credentials.Credentials) -> None:
    self.bq_client = bigquery_utils.CloudBigQueryUtils(config.project_id,
                                                       credentials)
    self.config = config

  def _check_target(self, target: str):
    if not target:
      raise ValueError(f'Target was not specified')
    for t in self.config.targets:
      if t.name == target:
        return
    raise ValueError('Unknown target ' + target)

  def execute_sql_script(self,
                         script_name: str,
                         target: str,
                         params: Dict[str, str] = None):
    self._check_target(target)
    if not params:
      params = {}
    params['target'] = target
    return self.bq_client.execute_scripts(script_name, self.config.dataset_id,
                                          params)

  def load_products(self,
                    target: str,
                    *,
                    in_stock_only: bool = False,
                    long_description: bool = False,
                    category_only: bool = False,
                    product_only: bool = False,
                    maxrows: int = 0):
    self._check_target(target)
    where_clause = ''
    if in_stock_only:
      where_clause = 'WHERE p.in_stock = 1'
    if long_description:
      if where_clause:
        where_clause += ' AND '
      else:
        where_clause = 'WHERE '
      where_clause += 'length(p.title) > 90 and length(p.description) > 90 and ad.ad_description1 is null'
    if category_only:
      if where_clause:
        where_clause += ' AND '
      else:
        where_clause = 'WHERE '
      where_clause += "pdsa_custom_labels not like 'product_%'"
    elif product_only:
      if where_clause:
        where_clause += ' AND '
      else:
        where_clause = 'WHERE '
      where_clause += "pdsa_custom_labels like 'product_%'"
    if maxrows > 0:
      where_clause += '\nLIMIT ' + str(maxrows)
    params = {"WHERE_CLAUSE": where_clause}
    products = self.execute_sql_script('get-products.sql', target, params)
    logging.info(f'Fetched {products.total_rows} products')
    return products

  def load_labels(self,
                  target: str, *,
                  category_only: bool = False,
                  product_only: bool = False):
    self._check_target(target)
    if category_only:
      params = {'WHERE_CLAUSE': "WHERE trim(lab) NOT LIKE 'product_%'"}
    elif product_only:
      params = {'WHERE_CLAUSE': "WHERE trim(lab) LIKE 'product_%'"}
    else:
      params = {"WHERE_CLAUSE": ""}
    labels = self.execute_sql_script('get-labels.sql', target, params)
    logging.info(f'Fetched {labels.total_rows} labels')
    return labels

  def load_page_feed(self, target: str):
    self._check_target(target)
    # Execute a SQL script (TODO: read its name from config) to get data for DSA page feed
    # The contract for the script:
    #   we expect 2-columns: 'Page_URL' and 'Custom_label'
    #   both columns should not be empty or NULL
    #   the Custom_label column can contain one or many label, separated by ';'
    #   values in Page_URL column should be unique
    # NOTE: currently we don't validate all those invariants, only assume they
    data = self.execute_sql_script('get-page-feed.sql', target)
    return data

  def update_product(self, target: str, product_id: str, data):
    self._check_target(target)
    sql = """MERGE `{project_id}.{dataset}.Ads_Preview_Products_{target}` T
USING (select @product_id as product_id, @custom_description as custom_description) S
ON T.product_id = S.product_id
WHEN MATCHED AND S.custom_description IS NULL OR Length(S.custom_description) = 0 THEN
  DELETE
WHEN MATCHED THEN
  UPDATE SET ad_description1 = S.custom_description
WHEN NOT MATCHED THEN
  INSERT (product_id, ad_description1) VALUES (product_id, custom_description)
    """
    query_parameters = [
        bigquery.ScalarQueryParameter("product_id", "STRING", product_id),
        bigquery.ScalarQueryParameter("custom_description", "STRING",
                                      data['custom_description']),
    ]
    params = {'target': target, 'product_id': product_id}
    return self.bq_client.execute_query(sql, self.config.dataset_id, params,
                                        query_parameters)
