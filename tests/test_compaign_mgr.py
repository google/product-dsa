# coding=utf-8
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
import csv
from dataclasses import dataclass
from typing import Any, Dict, List, Union
from app.context import ContextOptions
from common.config_utils import Config, ConfigTarget
from app.main import Context
from app.campaign_mgr import CampaignMgr, AdCustomizerGenerator

def get_products_data():
  return [{
    "custom_description":
        "",
    "data_date":
        "2021-12-15",
    "latest_date":
        "2021-12-15",
    "product_id":
        "online:ru:RU:145155873",
    "merchant_id":
        "123",
    "offer_id":
        "145155873",
    "title":
        "Wi-Fi router Keenetic 4G KN-1211",
    "description":
        "Интернет-центр Keenetic 4G KN-1211- компактный роутер, поддерживающий IPv6 и Wi-Fi стандарта 802.11 b/g/n, подключается к сетям 3G, 4G/LTE посредством USB-модема. Работает на частоте 2.5 ГГц с предельной скоростью передачи данных 300 Мбит/с.",
    "link":
        "link",
    "image_link":
        "image_link",
    "additional_image_links": ["additional_image_link"],
    "content_language":
        "en",
    "target_country":
        None,
    "brand":
        "MYKA",
    "color":
        "Gold",
    "item_group_id":
        "110011792",
    "google_product_category_path":
        None,
    "product_type":
        "Customer > Электроника > Ноутбуки и периферия для компьютеров > Периферия для компьютеров > Сетевое оборудование",
    "channel":
        "online",
    "adult":
        None,
    "availability_date":
        None,
    "condition":
        "new",
    "price": {
        "value": "2890",
        "currency": "RUB"
    },
    "sale_price": {
        "value": "2890",
        "currency": "RUB"
    },
    "sale_price_effective_start_date":
        None,
    "sale_price_effective_end_date":
        None,
    "in_stock":
        "1",
    "custom_labels": {
        "label_0": "",
        "label_1": "msk-spb",
        "label_2": "PDSA_PRODUCT",
        "label_3": "",
        "label_4": ""
    },
    "discount":
        "0",
    "pdsa_custom_labels":
        "product_145155873"
  }]


@dataclass
class SchemaField:
  name: str
  field_type: str
  fields: List['SchemaField'] = None
  mode: str = ''


class ProductItem:
  def __init__(self, data: dict)  -> None:
    self._data = data

  def __getattribute__(self, name: str) -> Any:
    try:
      return object.__getattribute__(self, name)
    except AttributeError:
      return self._data.get(name)

  def __setattr__(self, name: str, value: Any) -> None:
    if name == '_data':
      object.__setattr__(self, name, value)
      #setattr(self, name, value)
    else:
      self._data[name] = value

  def __getitem__(self, key):
    return self._data.get(key)

  def __setitem__(self, key, item):
    self._data[key] = item

  def __len__(self):
    return len(self._data)


class Products:
  def _get_field_meta(self, item):
    field = SchemaField(name=item[0], field_type="STRING")
    if isinstance(item[1], List):
      field.mode = 'REPEATED'
    if isinstance(item[1], Dict):
      field.field_type = 'RECORD'
      field.fields = []
      for sub_item in item[1].items():
        field.fields.append(self._get_field_meta(sub_item))
    return field

  def __init__(self, data) -> None:
    self.data = data
    obj = data[0]
    schema = []
    for item in obj.items():
      schema.append(self._get_field_meta(item))
    self.schema = schema

  def __iter__(self):
    for obj in self.data:
      yield ProductItem(obj)


def get_products(products: Union[List,None] = None):
  return Products(products if products else get_products_data())


def test_generate_csv(tmpdir):
  config = Config()
  target = ConfigTarget()
  context = Context(config, target, None, ContextOptions(tmpdir, "images", images_dry_run=True))
  context.gcs_bucket = None
  products = get_products()
  compaign_mgr = CampaignMgr(context, products)
  output_csv_path = compaign_mgr.generate_csv()

  assert output_csv_path
  with open(output_csv_path, 'r', encoding='utf-16') as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
      print(row)

def test_filter_images(tmpdir):
  config = Config()
  target = ConfigTarget()
  target.image_filter = '*1*.jpg;!*_s.jpg;'  # include product1*.jpg, exclude product1_s.jpg
  target.init_image_filter()
  context = Context(
      config, target, None,
      ContextOptions(tmpdir, "images", images_dry_run=True, images_on_gcs=False))
  context.gcs_bucket = None
  products = get_products_data()
  products[0]["image_link"] = 'http://customer.shop/products/product1.jpg'
  products[0]["additional_image_links"] = [
      'http://customer.shop/products/product1_s.jpg',
      'http://customer.shop/products/product1_b.jpg',
      'http://customer.shop/products/product1_m.jpg'
  ]
  products_rs = get_products(products)
  compaign_mgr = CampaignMgr(context, products_rs)
  product = next(iter(products_rs))
  files_md = {}
  # act
  images = compaign_mgr._get_images(product, 1200, files_md)
  # assert
  pid = products[0]['offer_id']
  assert files_md[f'{pid}_product1_ls.jpg']
  assert files_md[f'{pid}_product1_sq.jpg']
  assert files_md[f'{pid}_product1_b_ls.jpg']
  assert files_md[f'{pid}_product1_b_sq.jpg']
  assert files_md[f'{pid}_product1_m_ls.jpg']
  assert files_md[f'{pid}_product1_m_sq.jpg']
