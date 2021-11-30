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

from PIL import Image
import logging
import os

# Acceptable landscape ratio for image extensions
# https://support.google.com/google-ads/editor/answer/57755#zippy=%2Cimage-extensions
LANDSCAPE_RATIO = 1.91
LANDSCAPE_MIN_THRESHOLD = 1.5     # Min ratio at which to resize to landscape not square

logging.getLogger().setLevel(logging.INFO)

def resize(image_path, landscape = False):
  """Resize PIL image keeping ratio and using white background to follow
     size guidelines of image extensions.
     https://support.google.com/google-ads/editor/answer/57755#zippy=%2Cimage-extensions
     by default resizes the image to 1:1 ratio unless it should be landscape
  """
  image = Image.open(image_path)
  ratio = round(image.width/image.height , 2)
  if landscape:
    image_path = "{0}_ls{1}".format(*os.path.splitext(image_path))

  if ratio == 1 and not landscape or ratio == LANDSCAPE_RATIO and landscape:
    return image_path

  resize_width = image.width
  resize_height = image.height
  if not landscape:
    # Will resize to a square image
    if image.width > image.height:
      resize_height = image.width
    else:
      resize_width = image.height
  else:
    # Will resize to landscape image
    if ratio <= LANDSCAPE_RATIO:
      resize_width = round(image.height * LANDSCAPE_RATIO)
    else:
      resize_height = round(image.width / LANDSCAPE_RATIO)

  background = Image.new('RGBA', (resize_width, resize_height), (255, 255, 255, 255))
  offset = (round(
      abs(image.width - resize_width) / 2), round(abs(image.height - resize_height) / 2))
  background.paste(image, offset)

  try:
    background.convert('RGB').save(image_path)
    return image_path
  except Exception:
    logging.warning(f'Failed to resize image {image_path}')
