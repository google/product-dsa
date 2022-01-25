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

from PIL import Image
import logging
import os
import shutil
from typing import List
from common.utils import get_rss

# Acceptable landscape ratio for image extensions
# https://support.google.com/google-ads/editor/answer/57755#zippy=%2Cimage-extensions
LANDSCAPE_RATIO = 1.91
MINIMUM_DIMENSION = 300

logging.getLogger('PIL').setLevel(logging.INFO)


def _pad_image(image: Image, resize_width: int, resize_height: int,
               max_dimension: int, output_filepath: str):
  """Create a new image by inserting the original image into white rectangel of specified size"""
  offset = (round(abs(image.width - resize_width) / 2),
            round(abs(image.height - resize_height) / 2))
  with Image.new('RGB', (resize_width, resize_height),
                 (255, 255, 255)) as background:
    background.paste(image, offset)
    try:
      if max_dimension > 0 and (background.width > max_dimension or
                                background.height > max_dimension):
        background.thumbnail(size=(max_dimension, max_dimension))
      if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
        logging.debug(
            f'Resized image {os.path.basename(output_filepath)}: {background.size}, aspect ration: {background.width/background.height:.2f}'
        )
      background.save(output_filepath)
      return output_filepath
    except Exception as e:
      logging.error(f'Failed to resize image {output_filepath}: {e}')
      return ''


def _construct_file_path(filename, folder, filename_suffix):
  filename_parts = os.path.splitext(filename)
  filename_name = filename_parts[0]
  filename_ext = filename_parts[1]
  output_filepath = os.path.join(
      folder, f'{filename_name}{filename_suffix}{filename_ext}')
  return output_filepath


def resize(image_path: str,
           output_folder: str = None,
           max_dimension: int = 1200,
           *,
           dry_run: bool = False) -> List[str]:
  """Create two images, one square and another landscape to follow
     size guidelines of image extensions:
     * https://support.google.com/google-ads/editor/answer/57755#zippy=%2Cimage-extensions
     * https://support.google.com/google-ads/answer/9566341
     Supported image sizes for image extensions:
      1.91:1, minimum 600 x 314, recommended 1200x628
      1:1, minimum 300 x 300, recommended 1200x1200
     If image is square it's only resized to landscape, and on the contrary.
     When an image resized it's put on white background.

  Args:
    image_path: a local image path
    max_dimension: a max dimension for width/height after which image will be resized
    (to be with that width/heigh maximum)

  Returns:
    a 2-element array with local image paths,
    where the first is square and the second is landscape
  """
  image_filename = os.path.basename(image_path)
  if not output_folder:
    output_folder = os.path.split(image_path)[0]
  os.makedirs(output_folder, exist_ok=True)
  if dry_run:
    return [
        _construct_file_path(image_filename, output_folder, "_sq"),
        _construct_file_path(image_filename, output_folder, "_ls")
    ]
  output_image_path = None
  with Image.open(image_path) as image:
    ratio = round(image.width / image.height, 2)
    logging.debug(
        f'Processing image {image_path}, width: {image.width}, heigh: {image.height}, ratio: {ratio}'
    )
    if max_dimension > 0 and (image.width > max_dimension or
                              image.height > max_dimension):
      image.thumbnail(size=(max_dimension, max_dimension))
      output_image_path = os.path.join(output_folder, image_filename)
      image.save(output_image_path)
      logging.debug(f'Image too big, shrinked to {image.size}')
    elif image.width < MINIMUM_DIMENSION or image.height < MINIMUM_DIMENSION:
      if image.width < MINIMUM_DIMENSION and image.height < MINIMUM_DIMENSION:
        resize_width = resize_height = MINIMUM_DIMENSION
      elif image.width < MINIMUM_DIMENSION:
        resize_width = MINIMUM_DIMENSION
        resize_height = round(MINIMUM_DIMENSION / ratio)
      elif image.height < MINIMUM_DIMENSION:
        resize_height = MINIMUM_DIMENSION
        resize_width = round(MINIMUM_DIMENSION * ratio)
      output_image_path = os.path.join(output_folder, image_filename)
      image = Image.open(
          _pad_image(image, resize_width, resize_height, max_dimension,
                     output_image_path))
      logging.debug(f'Image too small, padded to 300px')

    image_paths = []
    # 1 create a square image
    resize_width = image.width
    resize_height = image.height
    sq_image_filepath = _construct_file_path(image_filename, output_folder,
                                             "_sq")
    if ratio == 1:
      shutil.copyfile(image_path, sq_image_filepath)
      logging.debug(
          f'Reusing image {os.path.basename(image_path)} as square: {sq_image_filepath}'
      )
      image_paths.append(sq_image_filepath)
    else:
      # Will resize to a square image
      if image.width > image.height:
        resize_height = image.width
      else:
        resize_width = image.height
      image_paths.append(
          _pad_image(image, resize_width, resize_height, 0, sq_image_filepath))

    # 2 create a landscape image
    resize_width = image.width
    resize_height = image.height
    ls_image_filepath = _construct_file_path(image_filename, output_folder,
                                             "_ls")
    if ratio == LANDSCAPE_RATIO:
      shutil.copyfile(image_path, ls_image_filepath)
      logging.debug(
          f'Reusing image {os.path.basename(image_path)} as landscape: {ls_image_filepath}'
      )
      image_paths.append(ls_image_filepath)
    else:
      # Will resize to landscape image
      if ratio <= LANDSCAPE_RATIO:
        resize_width = round(resize_height * LANDSCAPE_RATIO)
      else:
        resize_height = round(resize_width / LANDSCAPE_RATIO)
      image_paths.append(
          _pad_image(image, resize_width, resize_height, max_dimension,
                     ls_image_filepath))

  return image_paths
