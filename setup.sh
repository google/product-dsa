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

export PYTHONPATH="."
# Checking version/Installing Python
python3_installed() {
  local a b
  a=$(python3 --version 2>&1 | perl -pe 's/python *//i') ; b="3.8"
  [ "$( (echo "$a" ; echo "$b") | sort -V | head -1)" == "$b" ]
}
if python3_installed ; then
  echo "Detected Python >= 3.8"
else
  echo -e "${RED}"
  echo "Error: Python version < 3.8 - Product DSAs needs python 3.8+"
  exit
fi
# install and activate Python virtual environment
python3 -m venv .venv
. .venv/bin/activate
# install dependencies
python3 -m pip install -r requirements.txt


# run installation
python3 ./install/cloud_env_setup.py "$@"

# NOTE: despite other GCP services GAE supports only two regions: europe-west and us-central
GAE_LOCATION=europe-west
PROJECT_ID=$(gcloud config get-value project 2> /dev/null)

gcloud app create --region $GAE_LOCATION
gcloud app deploy -q
