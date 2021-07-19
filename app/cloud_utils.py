import os
import argparse
from urllib import parse
import importlib
import yaml
from google.cloud import storage
from google.api_core import exceptions

def get_file_content(uri):
  if uri.startswith('gs://'):
    return get_file_from_gcs(uri)
  elif os.path.exists(uri):
    with open(uri, 'r') as f:
      return f.read()
  raise ValueError(f'File {uri} wasn\'t found')

def get_file_from_gcs(uri):
  result = parse.urlparse(uri)
  # result.path will be '/path/to/blob', we need to strip the leading '/'.
  bucket_name, path = result.hostname, result.path[1:]
  client = storage.Client()
  try:
    bucket = client.get_bucket(bucket_name)
    content = bucket.get_blob(path).download_as_string().decode('utf-8')
    return content
  except exceptions.NotFound as e:
    raise ValueError(f'File {uri} wasn\'t found on Cloud Storage') from e
  except:
    print(f'Error fetching file {uri} from GCS')
    raise