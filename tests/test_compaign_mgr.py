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
import csv
from dataclasses import dataclass
from typing import Any, Dict, List
from app.context import ContextOptions
from common.config_utils import Config, ConfigTarget
from app.main import Context
from app.campaign_mgr import CampaignMgr, AdCustomizerGenerator

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


def get_products():
  return Products([
      {
          "data_date":
              "2021-12-15",
          "latest_date":
              "2021-12-15",
          "product_id":
              "online:en:US:110-01-1792-09",
          "merchant_id":
              "2510698",
          "offer_id":
              "110-01-1792-09",
          "title":
              "3D Engraved Bar Necklace in Gold Plating - Personalized Necklace with Names - Name Jewelry - Name Necklace - Christmas Gift for New Mom - Push Gift",
          "description":
              "The Dimensional Love 3D Bar Necklace represents a true love story and allows one to express creative freedom. Inspired by a writer who sits down to start a novel-the joy he or she feels when starting the first blank white page, you have the power to be the creator of your own love story rooting from your own special moments and personal expression. You may put whatever you desire into your necklace, your story, which will leave you with a meaningful piece to treasure forever. Express your love in all dimensions with four different sizes to personalize. Other features include: 1-4 inscriptions Classic print font Smooth, curved edges 18k Gold Plated box chain WHY THEY WILL LOVE IT: A perfect addition to any one’s daily wardrobe and eye-catching from every angle, at MYKA this necklace is definitely a favorite. A unique treasure for years to come, customize your story. MORE CHOICES: This necklace is also available in Sterling Silver, 18k Rose Gold Plating, and 18k Gold Vermeil. View our Bar Necklace Collection for more styles: there’s something perfect for everyone on your list! Show more Show less",
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
              "Apparel & Accessories > Jewelry > Necklaces",
          "product_type":
              "Gifts for Women > Apparel & Accessories > Jewelry > Necklace > Gold",
          "destinations": [{
              "name": "Shopping",
              "status": None,
              "approved_countries": ["US"],
              "pending_countries": [],
              "disapproved_countries": []
          }],
          "issues": [],
          "unique_product_id":
              "2510698|online:en:US:110-01-1792-09",
          "product_type_l1":
              "Gifts for Women ",
          "product_type_l2":
              " Apparel & Accessories ",
          "product_type_l3":
              " Jewelry ",
          "product_type_l4":
              " Necklace ",
          "product_type_l5":
              " Gold",
          "google_product_category_l1":
              "Apparel & Accessories ",
          "google_product_category_l2":
              " Jewelry ",
          "google_product_category_l3":
              " Necklaces",
          "google_product_category_l4":
              "",
          "google_product_category_l5":
              "",
          "channel":
              "online",
          "adult":
              None,
          "age_group":
              "adult",
          "availability_date":
              None,
          "condition":
              "new",
          "gender":
              "unisex",
          "material":
              "Gold",
          "price": {
              "value": "104.95",
              "currency": "USD"
          },
          "sale_price": {
              "value": "104.95",
              "currency": "USD"
          },
          "sale_price_effective_start_date":
              None,
          "sale_price_effective_end_date":
              None,
          "in_stock":
              "1",
          "custom_labels": {
              "label_0":
                  "3D Bar Necklaces",
              "label_1":
                  "Necklaces",
              "label_2":
                  "PDSA_PRODUCT",
              "label_3":
                  "Dimensional Love 3D Bar Necklace in 18k Gold Plating - The Perfect Gift.",
              "label_4":
                  "Generic OS19 - Mother gifts"
          },
          "discount":
              "0",
          "pdsa_custom_labels":
              "product_110-01-1792-09"
      },
  ])


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

