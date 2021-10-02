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
/*
  Gets a list of category labels used.

  The query only runs on the table of filtered products (i.e. in-stock and
  selected as part of the Products DSA run).

  Parameters:
  - project_id
  - dataset
  - target
*/

SELECT
  DISTINCT (pdsa_custom_labels)
FROM
  `{project_id}.{dataset}.Products_Filtered_{target}`
WHERE
  pdsa_custom_labels NOT LIKE 'product_%'