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
import os
from dataclasses import dataclass
from google.auth import credentials
from google.cloud import storage
from app.data_gateway import DataGateway
from common import config_utils, bigquery_utils


@dataclass
class ContextOptions:
  """Additional options for Context"""
  output_folder: str
  """Output folder path (relative to current dir or absolute) to place generated files into"""
  image_folder: str
  """Subfolder name/path of output folder to place product images into (should not contain '..')"""
  images_dry_run: bool = False
  """If True then images won't be downloaded and resized/padded (but image extensions still will be created)"""
  images_on_gcs: bool = False
  """True to keep images (downloaded and resized/padded) on GCS"""


class Context:

  def __init__(self, config: config_utils.Config,
               target: config_utils.ConfigTarget,
               credentials: credentials.Credentials, options: ContextOptions):
    self.config = config
    self.target = target
    self.credentials = credentials
    self.output_folder = options.output_folder or ''
    self.image_folder = options.image_folder or 'images'
    if target:
      self.output_folder = os.path.join(self.output_folder, target.name)
    self.data_gateway = DataGateway(config, credentials)
    self.storage_client = storage.Client(project=config.project_id,
                                         credentials=credentials)
    self.images_dry_run = options.images_dry_run
    self.images_on_gcs = True
    self.gcs_bucket = (config.project_id + '-pdsa') if config.project_id else None
    self.gs_base_path = f'gs://{self.gcs_bucket}/'
    if target:
      self.gs_base_path = self.gs_base_path + target.name + '/'
    if '..' in self.image_folder:
      raise ValueError(f"image folder setting should not contain '..'")
    self.gs_images_path = self.gs_base_path + self.image_folder + '/'
    self.gs_download_path = self.gs_base_path + self.image_folder + '-download/'

  def ensure_folders(self):
    if not os.path.isabs(self.output_folder):
      self.output_folder = os.path.abspath(self.output_folder)
    if self.output_folder:
      os.makedirs(self.output_folder, exist_ok=True)
