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
from io import TextIOWrapper
import os
from typing import Any, List, Dict
import requests
import logging
import zipfile
import zipstream
from urllib import parse
import posixpath
from datetime import datetime, timedelta
from google.cloud import storage
from google.api_core import exceptions
import smart_open as smart_open

logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('google.resumable_media._helpers').setLevel(logging.WARNING)

CHROME_USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36'


def generate_filename(path: str, *, suffix: str = None, extenssion: str = None) -> str:
  pair = os.path.splitext(os.path.basename(path))
  filename = pair[0]
  if suffix:
    filename += suffix
  if extenssion:
    filename += extenssion
  else:
    filename += pair[1]
  return filename


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
                  invalidate_cache: bool = False,
                  lastModified: str) -> str:
  """Download a remote file into a local folder."""
  if not local_path:
    if not folder:
      raise ValueError('folder should be specified if no local_path provided')
    os.makedirs(folder, exist_ok=True)
    parsed_uri = parse.urlparse(uri)
    file_name = os.path.basename(parsed_uri.path)
    local_path = os.path.join(folder, file_name)
  # Change the user agent because some websites don't like traffic from "non-browsers"
  headers = {'User-Agent': CHROME_USER_AGENT}
  try:
    if dry_run:
      return local_path, 304
    if lastModified:
      headers['if-modified-since'] = _datetime2str(lastModified)
    elif os.path.exists(local_path) and not invalidate_cache:
      headers['if-modified-since'] = _datetime2str(
          get_file_last_modified(local_path))
    # NOTE: it can be seemed logical to use etag here (and pass it in if-none-match header),
    # but the thing is that etags in GCS are different that normally from web servers
    with requests.get(uri, headers=headers) as response:
      if response.status_code == 304:
        logging.debug(f'Reusing local copy of file {uri} (304)')
        return local_path, 304
      if response.status_code == 200:
        with open(local_path, 'wb') as f:
          f.write(response.content)
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
          last_modified = _str2datetime(last_modified)
          set_file_last_modified(local_path, last_modified)
        return local_path, 200
      raise FileNotFoundError(
          f"Couldn't download file {uri}: {response.reason}")
  except BaseException as e:
    logging.error(f'Error occured during file {uri} download: {e}')
    raise


def copy_file_from_gcs(uri: str,
                       destination_file_name: str,
                       storage_client: storage.Client = None):
  """Copy a file on Cloud Storage to a local file"""
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  if not storage_client:
    storage_client = storage.Client()
  try:
    bucket = storage_client.get_bucket(bucket_name)
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


def get_file_from_gcs(uri: str, storage_client: storage.Client = None) -> str:
  """Read text file content from Cloud Storage url (in utf8)"""
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  if not storage_client:
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


def save_file_to_gcs(uri: str,
                     content: str,
                     storage_client: storage.Client = None):
  """Write text content to a file on GCS.
    Args:
      uri: a GCS path like gs://bucket/path/to/file
  """
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  if not storage_client:
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
                             storage_client: storage.Client = None
                            ) -> storage.Bucket:
  if not storage_client:
    storage_client = storage.Client()
  try:
    bucket = storage_client.get_bucket(bucket_name)
  except exceptions.NotFound:
    bucket = storage_client.create_bucket(bucket_name)
  return bucket


def get_gcs_bucket(bucket_name: str,
                   storage_client: storage.Client = None) -> storage.Bucket:
  if not storage_client:
    storage_client = storage.Client()
  try:
    bucket = storage_client.get_bucket(bucket_name)
  except exceptions.NotFound:
    bucket = None
  return bucket


def upload_file_to_gcs(local_file_path: str,
                       gcs_path: str,
                       storage_client: storage.Client = None):
  """Uploads a local file to project's a GCS bucket.

  Args:
    local_file_path - a local file path
    gcs_path - either a bucket name or a GCS path starting 'gs://',
               in latter case ot can be either a path to folder (ends with '/'
               (e.g. gs://bucket/path/to/) or a file path (gs://bucket/path/to/file)
  Return:
    a GCS path of uploaded file
  """
  file_name = os.path.basename(local_file_path)
  blob_path = file_name
  if gcs_path.startswith('gs://'):
    result = parse.urlparse(gcs_path)
    # result.path will be '/path/to/blob', we need to strip the leading '/'.
    bucket_name, path = result.hostname, result.path[1:]
    if path:
      if path.endswith('/'):
        blob_path = os.path.join(path, file_name)
      else:
        blob_path = path
  else:
    bucket_name = gcs_path

  bucket = get_or_create_gcs_bucket(bucket_name, storage_client)
  blob = bucket.blob(blob_path)
  blob.upload_from_filename(local_file_path)

  gcs_url = f'gs://{bucket_name}/{blob_path}'
  logging.debug(f'File {local_file_path} uploaded to {gcs_url}')
  return gcs_url


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


class GcsFile:

  def __init__(self, storage_client, gcs_file_path):
    self.storage_client = storage_client
    self.gcs_file_path = gcs_file_path

  def __iter__(self):
    f = smart_open.open(self.gcs_file_path,
                        "rb",
                        transport_params=dict(client=self.storage_client))
    return f


def gcs_archive_files(gs_paths: List[str],
                      storage_client: storage.Client = None,
                      *,
                      gs_path_base: str = '/') -> zipstream.ZipStream:
  """Archives files on GCS into a zip archive.
  Files are being streamed from GCS into an archive without keeping local
  copies or loading the whole archive into memory. So the size is unlimited.
  The archive itself can be on GCS as well.

  Args:
    gs_paths: a list of GCS urls of folders or files (folder should end with '/'),
              e.g. gs://bucket/, gs://bucket/folder/ gs://bucket/path/to/file
    storage_client
    gs_path_base: a GCS base path to calculate files paths inside archive,
                  should be common for all items in gs_paths
  Returns:
    ZipStream archive
  """
  if not storage_client:
    storage_client = storage.Client()
  zs = zipstream.ZipStream(compress_type=zipstream.ZIP_STORED, sized=False)
  gs_path_base_parsed = parse.urlparse(gs_path_base)
  for gs_path in gs_paths:
    if not gs_path.startswith('gs://'):
      raise ValueError(
          'GCS path should be a GCS url: gs://bucket or gs://bucket/path/ but got '
          + gs_path)
    gs_path_parsed = parse.urlparse(gs_path)
    if gs_path.endswith('/'):
      # folder
      bucket_name, prefix = gs_path_parsed.hostname, gs_path_parsed.path[1:]
      arcpath = posixpath.relpath(gs_path_parsed.path,
                                  start=gs_path_base_parsed.path)
      blobs = storage_client.list_blobs(bucket_name,
                                        prefix=prefix,
                                        delimiter='/')
      for blob in blobs:
        if blob.name == prefix:
          continue
        gcs_file = f'gs://{bucket_name}/{blob.name}'
        zs.add(GcsFile(storage_client, gcs_file),
               arcpath + '/' + posixpath.basename(blob.name))
    else:
      # file
      arcname = posixpath.relpath(gs_path_parsed.path,
                                  start=gs_path_base_parsed.path)
      zs.add(GcsFile(storage_client, gs_path), arcname)

  return zs


def get_blobs_metadata(gs_folder_path: str, storage_client: storage.Client = None) -> Dict[str,str]:
  """Returns a mapping from file (blob) name on GCS to its last modified timestamp """
  if not storage_client:
    storage_client = storage.Client()

  result = parse.urlparse(gs_folder_path)
  bucket_name, prefix = result.hostname, result.path[1:]
  blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter='/')
  return {
      os.path.basename(blob.name): blob.updated
      for blob in blobs
      if blob.name != prefix  # skip the "folder"
  }


def gcs_delete_folder_files(filter,
                            gs_folder_path: str,
                            storage_client: storage.Client = None):
  if not storage_client:
    storage_client = storage.Client()
  result = parse.urlparse(gs_folder_path)
  bucket_name, prefix = result.hostname, result.path[1:]
  blobs: List[storage.Blob] = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter='/')
  for blob in blobs:
    if filter(blob):
      logging.debug(f'Deleting GCS-file {blob.public_url}')
      blob.delete()


def download_file_to_gcs(uri: str,
                         gs_uri: str,
                         storage_client: storage.Client = None):
  headers = {'User-Agent': CHROME_USER_AGENT}
  # TODO: support dry_run
  try:
    result = parse.urlparse(gs_uri)
    # result.path will be '/path/to/blob', we need to strip the leading '/'.
    bucket_name, gs_file_path = result.hostname, result.path[1:]
    #parsed_uri = parse.urlparse(uri)
    #file_name = os.path.basename(parsed_uri.path)
    if not storage_client:
      storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(gs_file_path)
    last_modified = None
    if blob:
      # fetch metadata
      print(blob.metadata)
      last_modified = blob.metadata.get('last-modified', None)

    with smart_open.open(gs_uri,
                         "wb",
                         transport_params=dict(client=storage_client)) as f:
      f.writelines()
      if last_modified:
        headers['if-modified-since'] = last_modified
      with requests.get(uri, headers=headers) as response:
        if response.status_code == 304:
          logging.debug(f'Reusing local copy of file {uri} (304)')
          return gs_uri
        if response.status_code == 200:
          f.writelines(response.content)
          last_modified = response.headers.get('Last-Modified')
          if last_modified:
            if not blob:
              blob = bucket.get_blob(gs_file_path)
            blob.metadata = {
                **(blob.metadata or {}),
                **{
                    'last-modified': last_modified
                }
            }
            blob.patch()
          return gs_uri
        raise FileNotFoundError(
            f"Couldn't download file {uri}: {response.reason}")
  except BaseException as e:
    logging.error(f'Error occured during file {uri} download to GCS: {e}')
    raise


def zip(file_name: str, items: List[str]):
  """Create a zip archive from specified list of items (files/dirs)
  using standard zipfile package (everything loads in memory during archiving).
  Not recommended for large archives.
  """
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