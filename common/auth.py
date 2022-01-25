# Copyright 2022 Google LLC..
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

import argparse
import google.auth
from google.oauth2 import service_account  # type: ignore
from google_auth_oauthlib import flow
from google.auth import credentials

# NOTE bigquery.readonly is not covered by bigquery scope, do not remove it
_SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/bigquery',
    'https://www.googleapis.com/auth/bigquery.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata'
]


def add_auth_arguments(
    parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
  parser.add_argument(
      '--client-secrets-file',
      dest='client_secrets_file',
      help=
      'Path to user secrets file with oauth credentials (authenticating as a user).'
  )
  parser.add_argument(
      '--service-account-key-file',
      dest='service_account_file',
      help=
      'Path to service account key file (authenticating as a service account).')
  parser.add_argument(
      '--non-interactive',
      dest='non_interactive',
      action='store_true',
      help='Specify if using client-secrets-file option and running via ssh or remotely.')
  return parser


def get_credentials(args: argparse.Namespace,
                    scopes=_SCOPES) -> credentials.Credentials:
  if args.client_secrets_file:
    try:
      appflow = flow.InstalledAppFlow.from_client_secrets_file(
          args.client_secrets_file, scopes)
      if args.non_interactive:
        appflow.run_console()
      else:
        appflow.run_local_server()
      credentials = appflow.credentials
    except ValueError as e:
      raise Exception("Invalid json file for web app authenication") from e
  elif args.service_account_file:
    try:
      credentials = service_account.Credentials.from_service_account_file(
          args.service_account_file, scopes=scopes)
    except ValueError as e:
      raise Exception(
          "Invalid json file for service account authenication") from e
  else:
    # NOTE: if you use `gcloud auth application-default login` then the scopes here will be ignored,
    #       you should specify them as parameter --scopes for the gcloud command
    credentials, project = google.auth.default(scopes=scopes)

  return credentials
