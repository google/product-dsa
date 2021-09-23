#!/bin/bash
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

COLOR='\033[0;36m' # Cyan
RED='\033[0;31m' # Red Color
NC='\033[0m' # No Color

PROJECT_ID=$(gcloud config get-value project 2> /dev/null)
PROJECT_TITLE='Product DSA'
USER_EMAIL=$(gcloud config get-value account 2> /dev/null)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID | grep projectNumber | sed "s/.* '//;s/'//g")
SERVICE_ACCOUNT=$PROJECT_ID@appspot.gserviceaccount.com
GAE_LOCATION=europe-west

echo -e "${COLOR}Enabling APIs...${NC}"
gcloud services enable appengine.googleapis.com
gcloud services enable iap.googleapis.com

echo -e "${COLOR}Creating App Engine...${NC}"

# NOTE: despite other GCP services GAE supports only two regions: europe-west and us-central
gcloud app create --region $GAE_LOCATION

# build and deploy app to GAE:
echo -e "${COLOR}Building app...${NC}"
./build.sh
GIT_COMMIT=$(git rev-parse HEAD)
sed -i'.original' -e "s/GIT_COMMIT\s*:\s*.*$/GIT_COMMIT: '$GIT_COMMIT'/" app.yaml

echo -e "${COLOR}Deploying app to GAE...${NC}"
gcloud app deploy -q

# create IAP
echo -e "${COLOR}Creating oauth brand (consent screen) for IAP...${NC}"
gcloud alpha iap oauth-brands create --application_title="$PROJECT_TITLE" --support_email=$USER_EMAIL

# create OAuth client for IAP
echo -e "${COLOR}Creating OAuth client for IAP...${NC}"
# TODO: ideally we need to parse the response from the previous command to get brand full name
gcloud alpha iap oauth-clients create projects/$PROJECT_NUMBER/brands/$PROJECT_NUMBER --display_name=iap \
  --format=json 2> /dev/null |\
  python3 -c "import sys, json; res=json.load(sys.stdin); i = res['name'].rfind('/'); print(res['name'][i+1:]); print(res['secret'])" \
  > .oauth
# Now in .oauth file we have two line, first client id, second is client secret
lines=()
while IFS= read -r line; do lines+=("$line"); done < .oauth
IAP_CLIENT_ID=${lines[0]}
IAP_CLIENT_SECRET=${lines[1]}

TOKEN=$(gcloud auth print-access-token)

# Enable IAP for AppEngine
# (source:
#   https://cloud.google.com/iap/docs/managing-access#managing_access_with_the_api
#   https://cloud.google.com/iap/docs/reference/app-engine-apis)
echo -e "${COLOR}Enabling IAP for App Engine...${NC}"
curl -X PATCH -H "Content-Type: application/json" \
 -H "Authorization: Bearer $TOKEN" \
 --data "{\"iap\": {\"enabled\": true, \"oauth2ClientId\": \"$IAP_CLIENT_ID\", \"oauth2ClientSecret\": \"$IAP_CLIENT_SECRET\"} }" \
 "https://appengine.googleapis.com/v1/apps/$PROJECT_ID?alt=json&update_mask=iap"

# Grant access to the current user
echo -e "${COLOR}Granting user $USER_EMAIL access to the app through IAP...${NC}"
gcloud alpha iap web add-iam-policy-binding --resource-type=app-engine --member="user:$USER_EMAIL" --role='roles/iap.httpsResourceAccessor'

echo -e "\n${COLOR}Done!${NC}"