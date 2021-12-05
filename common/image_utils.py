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
from typing import List

# Acceptable landscape ratio for image extensions
# https://support.google.com/google-ads/editor/answer/57755#zippy=%2Cimage-extensions
LANDSCAPE_RATIO = 1.91
LANDSCAPE_MIN_THRESHOLD = 1.5  # Min ratio at which to resize to landscape not square


def __doResize(image: Image, resize_width: int, resize_height: int,
               image_path: str, suffix: str):
  offset = (round(abs(image.width - resize_width) / 2),
            round(abs(image.height - resize_height) / 2))
  with Image.new('RGB', (resize_width, resize_height),
                 (255, 255, 255)) as background:
    background.paste(image, offset)

    path = os.path.split(image_path)
    image_folder = path[0]
    image_filename_parts = os.path.splitext(path[1])
    image_filename_name = image_filename_parts[0]
    image_filename_ext = image_filename_parts[1]
    output_image_filepath = os.path.join(
        image_folder, f'{image_filename_name}{suffix}{image_filename_ext}')
    try:
      background.save(output_image_filepath)
      return output_image_filepath
    except Exception as e:
      logging.error(f'Failed to resize image {image_path}: {e}')


def resize(image_path: str, max_dimension: int = 1200) -> List[str]:
  """Create two images, one square and another landscape to follow
     size guidelines of image extensions.
     (https://support.google.com/google-ads/editor/answer/57755#zippy=%2Cimage-extensions)
     Supported image sizes for image extensions:
      1.91:1, minimum 600 x 314
      1:1, minimum 300 x 300
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
  with Image.open(image_path) as image:
    ratio = round(image.width / image.height, 2)
    # TODO[segy]: currently we ignore image dimensions but
    # we could skip small images that violate image extension requirements,
    # or enlarge them to the minimum dimentions.
    logging.debug(
        f'Resizing {image_path}, width: {image.width}, heigh: {image.height}, ratio: {ratio}'
    )
    if max_dimension > 0 and (image.width > max_dimension or
                              image.height > max_dimension):
      image.thumbnail(size=(max_dimension, max_dimension))
      image.save(image_path)
      logging.debug(f'Image shunk to {max_dimension}px')

    keep_original = False
    image_paths = []
    resize_width = image.width
    resize_height = image.height
    # 1 create a square image
    if ratio == 1:
      image_paths.append(image_path)
      keep_original = True
    else:
      # Will resize to a square image
      if image.width > image.height:
        resize_height = image.width
      else:
        resize_width = image.height
      sq_image_filepath = __doResize(image, resize_width, resize_height,
                                     image_path, '_sq')
      image_paths.append(sq_image_filepath or '')

    # 2 create a landscape image
    if ratio == LANDSCAPE_RATIO:
      image_paths.append(image_path)
      keep_original = True
    else:
      # Will resize to landscape image
      if ratio <= LANDSCAPE_RATIO:
        resize_width = round(image.height * LANDSCAPE_RATIO)
      else:
        resize_height = round(image.width / LANDSCAPE_RATIO)
      ls_image_filepath = __doResize(image, resize_width, resize_height,
                                     image_path, '_ls')
      image_paths.append(ls_image_filepath or '')

  if not keep_original:
    # we didn't use original image
    # (we had to resize it as new images for both square and landspace),
    # so we can remove the original
    os.remove(image_path)

  return image_paths
