#!/bin/bash
#
# Copyright 2022 Google LLC
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

# This is the main installation script for Product DSA in GCP environment.
# It installs a GAE Web App (using install-web.sh) and
# grant the GAE service account additional roles required for executing setup.
# Setup itself is executed from within the application (or via setup.sh).
COLOR='\033[0;36m' # Cyan
RED='\033[0;31m' # Red Color
NC='\033[0m' # No Color

PROJECT_ID=$(gcloud config get-value project 2> /dev/null)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="csv(projectNumber)" | tail -n 1)
SERVICE_ACCOUNT=$PROJECT_ID@appspot.gserviceaccount.com

# check the billing
BILLING_ENABLED=$(gcloud beta billing projects describe $PROJECT_ID --format="csv(billingEnabled)" | tail -n 1)
if [[ "$BILLING_ENABLED" = 'False' ]]
then
  echo -e "${RED}The project $PROJECT_ID does not have a billing enabled. Please activate billing${NC}"
  exit
fi

echo -e "${COLOR}Enabling APIs...${NC}"
gcloud services enable appengine.googleapis.com
gcloud services enable iap.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable iamcredentials.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable bigquerydatatransfer.googleapis.com
gcloud services enable sheets.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable pubsub.googleapis.com


# deploy AppEngine application
./install-web.sh


# Grant GAE service account with the BigQuery Admin role so it could create data transfers
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SERVICE_ACCOUNT --role=roles/bigquery.admin
# Grant GAE service account with the Pub/Sub Admin role so it could create a DT with Pub/Sub notifications
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SERVICE_ACCOUNT --role=roles/pubsub.admin

# Grant BigQuery DTS service permissions (iam.serviceAccountTokenCreator) on the GAE service account
# But DTS SA doesn't exist right after the API enabled, so we have to call any DT method to trigger its creation
TOKEN=$(gcloud auth print-access-token)
gcloud services enable bigquerydatatransfer.googleapis.com
curl -X GET -H "Content-Type: application/json" \
 -H "Authorization: Bearer $TOKEN" \
 "https://bigquerydatatransfer.googleapis.com/v1/projects/$PROJECT_ID/transferConfigs"
# and after that we can grant DTS SA the needed permissions
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-bigquerydatatransfer.iam.gserviceaccount.com" --role=roles/iam.serviceAccountTokenCreator

# Allow the Pub/Sub service (Service Agent) to create Identity Tokens on behalf of a service account:
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com --role=roles/iam.serviceAccountTokenCreator

echo -e "\n${COLOR}Done!${NC}"
