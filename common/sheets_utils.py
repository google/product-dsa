# coding=utf-8
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
import logging
from googleapiclient.discovery import build
from google.auth import credentials

logging.getLogger().setLevel(logging.INFO)
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)


class GoogleSpreadsheetUtils(object):
  """This class provides methods to simplify BigQuery API usage."""

  def __init__(self, credentials: credentials.Credentials):
    self.sheetsAPI = build('sheets', 'v4', credentials=credentials)

  def update_values(self, docid: str, range, values):
    result = self.sheetsAPI.spreadsheets().values().update(
        spreadsheetId=docid,
        range=range,
        valueInputOption='USER_ENTERED',
        body={
            "range": range,
            "majorDimension": "ROWS",
            "values": values
        }).execute()
    logging.info(f'Spreadsheet {docid} updated')