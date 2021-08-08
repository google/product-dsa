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
NC='\033[0m' # No Color

PROJECT_ID=$(gcloud config get-value project 2> /dev/null)

enable_apis() {
  echo -e "${COLOR}Enabling APIs:${NC}"
  # Google BigQuery
  echo -e "${COLOR}\tGoogle BigQuery API...${NC}"
  gcloud services enable bigquery.googleapis.com
  # Google BigQuery
  echo -e "${COLOR}\tGoogle BigQuery Data Transfer API...${NC}"
  gcloud services enable bigquerydatatransfer.googleapis.com
  echo -e "${COLOR}\tGoogle Sheets API...${NC}"
  gcloud services enable sheets.googleapis.com
}

# enable required APIs
enable_apis

export PYTHONPATH="."
# install and activate Python virtual environment
python3 -m venv .venv
. .venv/bin/activate
# install dependencies
python3 -m pip install -r requirements.txt


# run installation
python3 ./install/cloud_env_setup.py "$@"

