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

-- Gets a list of labels with numbers of products having each label
--
-- The query only runs on the table of filtered products (i.e. in-stock and
-- selected as part of the Products DSA run)
/*
Parameters:
  - project_id
  - dataset
  - merchant_id
*/

WITH labels AS (
  SELECT split(pdsa_custom_labels,';') as label
  FROM `{project_id}.{dataset}.Products_{merchant_id}_Filtered`
  WHERE
    LENGTH(IFNULL(link,'')) > 0  AND
    LENGTH(IFNULL(pdsa_custom_labels,'')) > 0
)
SELECT lab as label, count(1) as count
FROM labels
CROSS JOIN UNNEST(labels.label) AS lab
GROUP BY 1