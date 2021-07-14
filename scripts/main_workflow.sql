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

-- Creates a table that represents PageFeeds from the filtered products view
--
-- PageFeeds are used to upload DSAs by targetting specific URLs
-- they are composed of URL for the DSA landing page and a targeting label
-- This table can be exported to CSV and uploaded to Google Ads

CREATE OR REPLACE TABLE `{project_id}.{dataset}.product_page_feeds_{merchant_id}`
AS (
  SELECT
    link AS Page_URL,
    CONCAT('product_', offer_id) AS Custom_label,
    -- CONCAT('type_', product_type_l1) AS Custom_label,
  FROM `{project_id}.{dataset}.filtered_product_view_{merchant_id}`
)
