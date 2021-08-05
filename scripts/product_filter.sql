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
-- based on a specific criteria
--
-- This filtered view includes a subset of the products in the products feed
-- and only some of the product details. The filtering can be done based on
-- different criteria like "custom label" or "product category"
-- The query only runs on in-stock products from the latest data transfer

CREATE OR REPLACE VIEW `{project_id}.{dataset}.filtered_product_view_{merchant_id}`
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
    custom_labels,
    item_group_id,
    google_product_category_path,
    product_type,
    destinations,
    issues,
    CONCAT(CAST(Products.merchant_id AS STRING), '|', product_id) AS unique_product_id,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(0)], 'N/A') AS product_type_l1,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(1)], 'N/A') AS product_type_l2,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(2)], 'N/A') AS product_type_l3,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(3)], 'N/A') AS product_type_l4,
    IFNULL(SPLIT(product_type, '>')[SAFE_OFFSET(4)], 'N/A') AS product_type_l5,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(0)], 'N/A') AS google_product_category_l1,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(1)], 'N/A') AS google_product_category_l2,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(2)], 'N/A') AS google_product_category_l3,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(3)], 'N/A') AS google_product_category_l4,
    IFNULL(SPLIT(google_product_category_path, '>')[SAFE_OFFSET(4)], 'N/A') AS google_product_category_l5,
    IF(availability = 'in stock', 1, 0) AS in_stock,
  FROM
    `{project_id}.{dataset}.Products_{merchant_id}` AS Products,
    LatestDate
  WHERE
    _PARTITIONDATE = LatestDate.latest_date
    AND availability = 'in stock'
    -- AND custom_labels.label_0 = filter_label
    -- TODO: Change to 100,000 in the future
    LIMIT 100
);

