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
import pytest
from PIL import Image
from common.image_utils import resize

def test_resize(tmpdir):

  def gen_images(input_folder):
    image_path = os.path.join(input_folder, 'image1.jpg')
    with Image.new('RGB', size=(100, 100), color=(0, 0, 0)) as image:
      image.save(image_path)
    yield image_path
    image_path = os.path.join(input_folder, 'image2.jpg')
    with Image.new('RGB', size=(100, 400), color=(0, 0, 0)) as image:
      image.save(image_path)
    yield image_path
    image_path = os.path.join(input_folder, 'image3.jpg')
    with Image.new('RGB', size=(400, 100), color=(0, 0, 0)) as image:
      image.save(image_path)
    yield image_path

  # arrange
  input_folder = os.path.join(tmpdir, 'input')
  os.makedirs(input_folder, exist_ok=True)
  for image_path in gen_images(input_folder):
    # act
    print(os.path.basename(image_path))
    image_paths = resize(image_path, tmpdir)
    # assert
    assert len(image_paths) == 2
    with Image.open(image_paths[0]) as image:
      # first is square
      print('\t', image.size)
      assert image.width >= 300 and image.width >= 300
      assert image.width == image.height
    with Image.open(image_paths[1]) as image:
      # second is landscape
      print('\t', image.size)
      assert image.width >= 300 and image.width >= 300
      assert round(image.width / image.height, 2) == 1.91
