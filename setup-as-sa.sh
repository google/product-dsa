#
# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# The script initialize Google Cloud infrastructure for a project 
# using a default App Engine service account in the current project.

USER_EMAIL=$(gcloud config get-value account 2> /dev/null)
PROJECT_ID=$(gcloud config get-value project 2> /dev/null)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID | grep projectNumber | sed "s/.* '//;s/'//g")
SERVICE_ACCOUNT=$PROJECT_ID@appspot.gserviceaccount.com

gcloud iam service-accounts keys create service_account.json --iam-account=$SERVICE_ACCOUNT

# Grant GAE service account with the BigQuery Admin role so it could create data transfers
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SERVICE_ACCOUNT --role=roles/bigquery.admin
# Grant GAE service account with the Pub/Sub Admin role so it could create a DT with Pub/Sub notifications
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SERVICE_ACCOUNT --role=roles/pubsub.admin

# Grant BigQuery DTS service permissions (iam.serviceAccountTokenCreator) on the GAE service account
# But DTS SA doesn't exit right after the API enabled, so we have to call any DT method to trigger its creation
TOKEN=$(gcloud auth print-access-token)
gcloud services enable bigquerydatatransfer.googleapis.com
curl -X GET -H "Content-Type: application/json" \
 -H "Authorization: Bearer $TOKEN" \
 "https://bigquerydatatransfer.googleapis.com/v1/projects/$PROJECT_ID/transferConfigs"
# and after that we can grant DTS SA the needed permissions
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-bigquerydatatransfer.iam.gserviceaccount.com" --role='roles/iam.serviceAccountTokenCreator'

./setup.sh --service-account-key-file service_account.json --user-email $USER_EMAIL "$@"
