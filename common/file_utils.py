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
from io import TextIOWrapper
import os
from typing import List
import requests
import zipfile
from urllib import parse
from google.cloud import storage
from google.api_core import exceptions
from common import image_utils

CHROME_USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36'


def get_file_content(uri: str):
  """Read file content supporting file paths on Cloud Storage (gs://)"""
  if uri.startswith('gs://'):
    return get_file_from_gcs(uri)
  elif os.path.exists(uri):
    with open(uri, 'r') as f:
      return f.read()
  elif uri.startswith(['http://', 'https://', 'ftp://', 'ftps://']):
    return requests.get(uri).text
  raise ValueError(f'File {uri} wasn\'t found')


def download_image(uri: str, folder: str):
  local_image_path = download_file(uri, folder)
  # Resize the local image to follow guidelines
  image_utils.resize(local_image_path)
  return local_image_path


def download_file(uri: str, folder: str):
  """Download a remote file into a local folder."""
  if not os.path.exists(folder):
    os.mkdir(folder)
  # Change the user agent because some websites don't like traffic from "non-browsers"
  headers = {'User-Agent': CHROME_USER_AGENT}
  response = requests.get(uri, headers=headers)
  if response.status_code == 200:
    result = parse.urlparse(uri)
    file_name = os.path.basename(result.path)
    local_path = os.path.join(folder, file_name)
    with open(local_path, 'wb') as f:
      f.write(response.content)
    return local_path
  raise Exception(f"Couldn't download file {uri}: {response.reason}")


def copy_file_from_gcs(uri: str, destination_file_name: str):
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  # NOTE: we're using ADC here (no explicit credentials passed)
  client = storage.Client()
  try:
    bucket = client.get_bucket(bucket_name)
    blob = bucket.get_blob(path)
    if blob:
      blob.download_to_filename(destination_file_name)
    else:
      raise ValueError(f'File {uri} wasn\'t found on Cloud Storage')
  except exceptions.NotFound as e:
    raise ValueError(f'File {uri} wasn\'t found on Cloud Storage') from e
  except Exception as e:
    print(f'Error fetching file {uri} from GCS: {str(e)}')
    raise


def get_file_from_gcs(uri: str):
  """Read file content from Cloud Storage url"""
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  # NOTE: we're using ADC here (no explicit credentials passed)
  client = storage.Client()
  try:
    bucket = client.get_bucket(bucket_name)
    blob = bucket.get_blob(path)
    if blob:
      content = blob.download_as_string().decode('utf-8')
    else:
      raise ValueError(f'File {uri} wasn\'t found on Cloud Storage')
    return content
  except exceptions.NotFound as e:
    raise ValueError(f'File {uri} wasn\'t found on Cloud Storage') from e
  except Exception as e:
    print(f'Error fetching file {uri} from GCS: {str(e)}')
    raise


def save_file_content(uri: str, content: str):
  if uri.startswith('gs://'):
    return save_file_to_gcs(uri, content)
  with open(uri, 'w') as file:
    file.write(content)


def save_file_to_gcs(uri: str, content: str):
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  # NOTE: we're using ADC here (no explicit credentials passed)
  client = storage.Client()
  try:
    bucket = client.get_bucket(bucket_name)
    content = bucket.get_blob(path).upload_from_string(content)
  except:
    print(f'Error on saving file {uri} to GCS')
    raise


def get_or_create_project_gcs_bucket(project_id: str, credentials) -> storage.bucket.Bucket:
  storage_client = storage.Client(project=project_id, credentials=credentials)
  bucket_name = project_id + '-pdsa'
  try:
    bucket = storage_client.get_bucket(bucket_name)
  except exceptions.NotFound:
    bucket = storage_client.create_bucket(bucket_name)
  return bucket


def upload_file_to_gcs(project_id: str, credentials, local_file_path: str):
  """Uploads a local file to project's GCS default bucket ({project_id}-pdsa."""
  bucket = get_or_create_project_gcs_bucket(project_id, credentials)
  file_name = os.path.basename(local_file_path)
  blob = bucket.blob(file_name)
  blob.upload_from_filename(local_file_path)


def open_relative_file(file_name: str) -> TextIOWrapper:
  """Opens a file for reading relatively to the current module."""
  working_directory = os.path.dirname(__file__)
  return open(os.path.join(working_directory, file_name), "rb")


def zip(file_name: str, items: List[str]):
  """Create a zip archive from specified list of items (files/dirs)"""
  basedir = os.path.dirname(file_name)
  with zipfile.ZipFile(file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for item in items:
      if os.path.isdir(item):
        for root, dirs, files in os.walk(item):
          for file in files:
            zipf.write(os.path.join(root, file),
                       os.path.relpath(os.path.join(root, file), basedir))
      else:
        zipf.write(item, os.path.relpath(item, basedir))
