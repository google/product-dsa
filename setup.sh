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

# The script initialize Google Cloud infrastructure for a project.
# Can be run many times without any harm.
# The minimum required Python version is 3.7 because it's the version installed in Cloud Shell
# It's an alternative way to initialize project infrastructure 
# as an alternative to executing setup from within application (which is recommended).

COLOR='\033[0;36m' # Cyan
RED='\033[0;31m' # Red Color
NC='\033[0m' # No Color

echo -e "${COLOR}Initialize Google Cloud infrastructure...${NC}"

export PYTHONPATH="."
# Checking version/Installing Python
python3_installed() {
  local a b
  a=$(python3 --version 2>&1 | perl -pe 's/python *//i') ; b="3.7"
  [ "$( (echo "$a" ; echo "$b") | sort -V | head -1)" == "$b" ]
}
if python3_installed ; then
  echo -e "${COLOR}Detected Python >= 3.7...${NC}"
else
  echo -e "${RED}Error: Python version < 3.7 - Product DSAs setup needs Python 3.7+${NC}"
  exit
fi
# install and activate Python virtual environment
python3 -m venv .venv
. .venv/bin/activate
# workaround possible issues with grpcio installation
pip install --upgrade pip wheel setuptools
# install dependencies
python3 -m pip install -r requirements.txt

# run installation
python3 ./install/cloud_env_setup.py "$@"
