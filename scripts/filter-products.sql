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

-- Filters the products from the latest snapshot of the GMC Data Transfer
-- based on product availability and presence of our custom labels:
-- PDSA_Product
-- The query only runs on in-stock products from the latest data transfer
/*
Parameters:
  - project_id
  - dataset
  - merchant_id
*/

-- Creates a command sepearated list of Product DSA's custom labels from custom_label GMC field
CREATE OR REPLACE FUNCTION {dataset}.combineLabels(custom_labels STRUCT<label0 STRING, label1 STRING, label2 STRING, label3 STRING, label4 STRING>, offer_id STRING)
RETURNS STRING
LANGUAGE js
AS r"""
  function getLabelValue(label, offer_id) {{
    if (!label) return null;
    if (label.toUpperCase().indexOf('PDSA_PRODUCT') === 0) {{
      return 'product_' + offer_id;
    }}
    let prefix = 'PDSA_CATEGORY_';
    if (label.toUpperCase().indexOf(prefix) === 0) {{
      return label.slice(prefix.length);
    }}
  }}
  let result = '';
  if (!custom_labels) return result;
  for (label of Object.values(custom_labels)) {{
    let norm_label = getLabelValue(label, offer_id);
    if (norm_label) {{
      if (result) result += '; '
      result += norm_label;
    }}
  }}
  return result;
""";

CREATE OR REPLACE VIEW `{project_id}.{dataset}.Products_{merchant_id}_Filtered`
AS (
  WITH
    LatestDate AS (
      SELECT
        MAX(_PARTITIONDATE) AS latest_date
      FROM
        `{project_id}.{dataset}.Products_{merchant_id}`
    )
  SELECT
    _PARTITIONDATE as data_date,
    LatestDate.latest_date,
    product_id,
    merchant_id,
    offer_id,
    title,
    description,
    link,
    image_link,
    additional_image_links,
    content_language,
    target_country,
    brand,
    color,
    item_group_id,
    google_product_category_path,
    product_type,
    destinations,
    issues,
    CONCAT(CAST(Products.merchant_id AS STRING), '|', product_id) AS unique_product_id,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(0)], '') AS product_type_l1,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(1)], '') AS product_type_l2,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(2)], '') AS product_type_l3,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(3)], '') AS product_type_l4,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(4)], '') AS product_type_l5,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(0)], '') AS google_product_category_l1,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(1)], '') AS google_product_category_l2,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(2)], '') AS google_product_category_l3,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(3)], '') AS google_product_category_l4,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(4)], '') AS google_product_category_l5,
    channel,
    adult,
    age_group,
    availability_date,
    condition,
    gender,
    material,
    price,
    sale_price,
    sale_price_effective_start_date,
    sale_price_effective_end_date,
    IF(availability = 'in stock', 1, 0) AS in_stock,
    custom_labels,
    ROUND ((price.value - sale_price.value)* 100/price.value, 1) AS discount,
    {dataset}.combineLabels(custom_labels, offer_id) AS pdsa_custom_labels
  FROM
    `{project_id}.{dataset}.Products_{merchant_id}` AS Products,
    LatestDate
  WHERE
    _PARTITIONDATE = LatestDate.latest_date
    AND availability = 'in stock'
    AND (custom_labels.label_0 like 'PDSA_%'
      OR custom_labels.label_1 like 'PDSA_%'
      OR custom_labels.label_2 like 'PDSA_%'
      OR custom_labels.label_3 like 'PDSA_%'
      OR custom_labels.label_4 like 'PDSA_%'
    )
);
