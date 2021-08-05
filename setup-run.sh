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
#
# Simplified version of setup that only runs Python scripts,
# assuming we have a client secrets file (client_secrets.json) exported from 
# https://console.cloud.google.com/apis/credentials

# It's required for local module resolutions
export PYTHONPATH="."

python3 ./install/cloud_env_setup.py --client-secrets-file client_secrets.json