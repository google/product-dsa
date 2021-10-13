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
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


class GoogleSpreadsheetUtils(object):
  """This class provides methods to simplify Google Spreadsheet API usage."""

  def __init__(self, credentials: credentials.Credentials):
    self.sheetsAPI = build('sheets', 'v4', credentials=credentials)

  def update_values(self, docid: str, range, values, clear_values=True):
    """Updates a range with values
      Args:
        docid: spreadsheet id
        range: range to overwrite in A1 notation (e.g. "Sheet!A1:Z")
        values: two dimentional array, first dimention is rows, second is columns (i.e. it's array of column values)
        clear_values: flags to clear the whole sheet before writing values
    """
    # Clear the contents of the spreadsheet
    if clear_values:
      self.sheetsAPI.spreadsheets().values().clear(
          spreadsheetId=docid,
          range=range,
          body={}).execute()
    # Write the new values
    result = self.sheetsAPI.spreadsheets().values().update(
        spreadsheetId=docid,
        range=range,
        valueInputOption='USER_ENTERED',
        body={
            "range": range,
            "majorDimension": "ROWS",
            "values": values
        }).execute()

  def get_values(self, docid: str, range):
    """Fetch values (as 2-dimentional array) from a range"""
    result = self.sheetsAPI.spreadsheets().values().get(
        spreadsheetId=docid, range=range, majorDimension="ROWS").execute()
    return result