-- Creates a table that represents PageFeeds from the filtered products view
--
-- PageFeeds are used to upload DSAs by targetting specific URLs
-- they are composed of URL for the DSA landing page and a targeting label
-- This table can be exported to CSV and uploaded to Google Ads

CREATE OR REPLACE TABLE `{project_id}.{dataset}.product_page_feed_{merchant_id}_{feedname}`
AS (
  SELECT
    link AS Page_URL,
    {custom_label_select}
    -- CONCAT('type_', product_type_l1) AS Custom_label,
  FROM `{project_id}.{dataset}.Products_{merchant_id}_Filtered`
)
