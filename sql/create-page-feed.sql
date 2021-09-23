-- Creates a table that represents PageFeeds from the filtered products view
--
-- PageFeeds are used to upload DSAs by targetting specific URLs
-- they are composed of URL for the DSA landing page and a targeting label
-- This table can be exported to CSV and uploaded to Google Ads
-- It only takes in-stock products into considertation

SELECT
  link AS Page_URL,
  pdsa_custom_labels AS Custom_label
FROM `{project_id}.{dataset}.Products_{merchant_id}_Filtered`
WHERE
  LENGTH(IFNULL(link,'')) > 0  AND
  LENGTH(IFNULL(pdsa_custom_labels,'')) > 0 AND
  in_stock = 1
