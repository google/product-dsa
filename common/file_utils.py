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
from typing import Any, List
import requests
import logging
import zipfile
import zipstream
from urllib import parse
from datetime import datetime, timedelta
from google.cloud import storage
from google.api_core import exceptions

logging.getLogger('urllib3').setLevel(logging.INFO)

CHROME_USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36'


def get_file_content(uri: str) -> str:
  """Read file content supporting file paths on Cloud Storage (gs://)"""
  if uri.startswith('gs://'):
    return get_file_from_gcs(uri)
  elif os.path.exists(uri):
    with open(uri, 'r') as f:
      return f.read()
  elif uri.startswith(('http://', 'https://', 'ftp://', 'ftps://')):
    return requests.get(uri).text
  raise FileNotFoundError(f'File {uri} wasn\'t found')


def download_file(uri: str,
                  local_path: str,
                  *,
                  folder: str = None,
                  dry_run: bool = False,
                  invalidate_cache: bool = False) -> str:
  """Download a remote file into a local folder."""
  if not local_path:
    if not folder:
      raise ValueError('Path should specified if no local_path provided')
    os.makedirs(folder, exist_ok=True)
    parsed_uri = parse.urlparse(uri)
    file_name = os.path.basename(parsed_uri.path)
    local_path = os.path.join(folder, file_name)
  # Change the user agent because some websites don't like traffic from "non-browsers"
  headers = {'User-Agent': CHROME_USER_AGENT}
  try:
    if dry_run:
      return local_path
    if os.path.exists(local_path) and not invalidate_cache:
      headers['if-modified-since'] = _datetime2str(
          get_file_last_modified(local_path))
    with requests.get(uri, headers=headers) as response:
      if response.status_code == 304:
        logging.debug(f'Reusing local copy of file {uri} (304)')
        return local_path
      if response.status_code == 200:
        with open(local_path, 'wb') as f:
          f.write(response.content)
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
          set_file_last_modified(local_path, _str2datetime(last_modified))
        return local_path
      raise FileNotFoundError(
          f"Couldn't download file {uri}: {response.reason}")
  except BaseException as e:
    logging.error(f'Error occured during file {uri} download: {e}')
    raise


def copy_file_from_gcs(uri: str, destination_file_name: str):
  """Copy a file on Cloud Storage to a local file"""
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
      raise FileNotFoundError(f'File {uri} wasn\'t found on Cloud Storage')
  except exceptions.NotFound as e:
    raise FileNotFoundError(f'File {uri} wasn\'t found on Cloud Storage') from e
  except Exception as e:
    print(f'Error on fetching file {uri} from GCS: {str(e)}')
    raise


def get_file_from_gcs(uri: str) -> str:
  """Read text file content from Cloud Storage url (in utf8)"""
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
      raise FileNotFoundError(f'File {uri} wasn\'t found on Cloud Storage')
    return content
  except exceptions.NotFound as e:
    raise FileNotFoundError(f'File {uri} wasn\'t found on Cloud Storage') from e
  except Exception as e:
    print(f'Error fetching file {uri} from GCS: {str(e)}')
    raise


def save_file_content(uri: str, content: str):
  """Write content to a file represented by an url"""
  if uri.startswith('gs://'):
    return save_file_to_gcs(uri, content)
  with open(uri, 'w') as file:
    file.write(content)


def save_file_to_gcs(uri: str, content: str):
  """Write text content to a file on GCS.
    Args:
      uri: a GCS path like gs://bucket/path/to/file
  """
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  # NOTE: we're using ADC here (no explicit credentials passed)
  storage_client = storage.Client()
  try:
    bucket = storage_client.get_bucket(bucket_name)
  except exceptions.NotFound:
    bucket = storage_client.create_bucket(bucket_name)
  try:
    bucket.blob(path).upload_from_string(content)
  except:
    print(f'Error on saving file {uri} to GCS')
    raise


def get_or_create_gcs_bucket(bucket_name: str,
                             credentials,
                             project_id: str = None) -> storage.Bucket:
  storage_client = storage.Client(project=project_id, credentials=credentials)
  try:
    bucket = storage_client.get_bucket(bucket_name)
  except exceptions.NotFound:
    bucket = storage_client.create_bucket(bucket_name)
  return bucket


def get_gcs_bucket(bucket_name: str,
                   credentials,
                   project_id: str = None) -> storage.Bucket:
  storage_client = storage.Client(project=project_id, credentials=credentials)
  try:
    bucket = storage_client.get_bucket(bucket_name)
  except exceptions.NotFound:
    bucket = None
  return bucket


def upload_file_to_gcs(bucket_name: str,
                       local_file_path: str,
                       credentials,
                       project_id: str = None):
  """Uploads a local file to project's a GCS bucket."""
  bucket = get_or_create_gcs_bucket(bucket_name, credentials, project_id)
  file_name = os.path.basename(local_file_path)
  blob = bucket.blob(file_name)
  blob.upload_from_filename(local_file_path)


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
        try:
          zipf.write(item, os.path.relpath(item, basedir))
        except BaseException as e:
          print(f'Zip failed to process {item} in {basedir}: {e}')
          raise


def gcs_get_signed_url(*,
                       client: storage.Client = None,
                       project_id: str = None,
                       credentials=None,
                       url: str = None,
                       filepath: str = None,
                       valid_for_min: int = 60) -> str:
  """Create a GCS signed url (publicly accessingle download url) for a blob

  Args:
    client - storage client, can be ommited but then project_id should be specified
    project_id - GCP project if no storage client specified (used to initialize bucket name)
    credentials - a service account's credentials (user's credentials won't work!)
    url - a full GCS url, e.g. gs://bucket/path/to/file
    filepath - a GCS file path (path/to/file) if url isn't specified
    valid_for_min - number of minitues while the signed url will be alive (default 60 min)
  """
  if not client:
    client = storage.Client(project=project_id, credentials=credentials)
  bucket_name = None
  if not url:
    if not project_id:
      raise ValueError(f'project_id must be specified if url is not provided')
    bucket_name = project_id + '-pdsa'
    #Initialize the bucket and blob
    if not filepath:
      raise ValueError('filepath must be specified if url is not provided')
  else:
    result = parse.urlparse(url)
    # result.path will be '/path/to/blob', we need to strip the leading '/'.
    bucket_name, filepath = result.hostname, result.path[1:]
    if not bucket_name or not filepath:
      raise ValueError('url is incorrect, expected gs://bucket/path/to/file')
  bucket = client.get_bucket(bucket_name)
  blob = bucket.get_blob(filepath)
  # Set the expiration time
  expiration_time = datetime.utcnow() + timedelta(minutes=valid_for_min)
  # Get the signed URL
  url = blob.generate_signed_url(
      version="v4",
      expiration=expiration_time,
      service_account_email=credentials.service_account_email,
      access_token=credentials.token)
  return url


def zip_stream(file_name: str, items: List[str]):
  """Create a zip archive from specified list of items using streaming"""
  zs = zipstream.ZipStream(compress_type=zipstream.ZIP_DEFLATED)
  for item in items:
    zs.add_path(item)
  with open(file_name, "wb") as f:
    f.writelines(zs)


_LAST_MODIFIED_DATETIME_FORMAT = '%a, %d %b %Y %X %Z'


def _str2datetime(str_time: str) -> datetime:
  """Convert datetime string in 'Fri, 17 Sep 2021 09:49:45 GMT' format to datetime """
  return datetime.strptime(
      str_time,
      #Fri, 27 Mar 2015 08:05:42 GMT
      _LAST_MODIFIED_DATETIME_FORMAT)


def _datetime2str(dt: datetime) -> str:
  """Convert datetime to string in 'Fri, 17 Sep 2021 09:49:45 GMT' format"""
  return dt.strftime(_LAST_MODIFIED_DATETIME_FORMAT)


def set_file_last_modified(file_path: str, dt: datetime):
  """Set file's modification timestamp"""
  dt_epoch = dt.timestamp()
  os.utime(file_path, (dt_epoch, dt_epoch))


def get_file_last_modified(file_path: str) -> datetime:
  """Return a file's modification timestamp"""
  return datetime.fromtimestamp(os.path.getmtime(file_path))