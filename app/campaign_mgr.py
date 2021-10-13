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
"""
Responsible for campaign creation of Product DSAs to upload into Google Ads
Uploading will initially be only supported through Google Ads Editor
i.e. The expected output is a CSV file.
"""
import collections
import csv
import re
import os
import decimal
import logging
from typing import Any, Dict, List
from google.auth import credentials
from google.cloud import storage
from google.api_core import exceptions
from common import config_utils, file_utils, sheets_utils
from forex_python.converter import CurrencyCodes

# Google Ads Editor header names
CAMP_NAME = 'Campaign'
CAMP_BUDGET = 'Budget'
# BUDGET_TYPE = 'Budget type'
# BID_STRATEGY_TYPE = 'Bid Strategy Type'
# TARGET_ROAS = 'Target ROAS'
# START_DATE = 'Start Date'
# END_DATE = 'End Date'
# AD_SCHEDULE = 'Ad Schedule'
# AD_ROTATION = 'Ad rotation'
# TARGETING_METHOD = 'Targeting method'
# EXCLUSION_MTHOD = 'Exclusion method'
DSA_WEBSITE = 'DSA Website'
DSA_LANG = 'DSA Language'
DSA_TARGETING_SOURCE = 'DSA targeting source'
DSA_PAGE_FEEDS = 'DSA page feeds'
ADGROUP_NAME = 'Ad Group'
ADGROUP_MAX_CPM = 'Max CPM'
ADGROUP_TARGET_CPM = 'Target CPM'
ADGROUP_TYPE = 'Ad Group Type'
TARGET_CONDITION = 'Dynamic Ad Target Condition 1'
TARGET_VALUE = 'Dynamic Ad Target Value 1'
AD_TYPE = 'Ad type'
AD_DESCRIPTION_ORIG = 'Description Line 1#Original'
AD_DESCRIPTION = 'Description Line 1'
IMAGE = 'Image'

# Default campaign names to use
PDSA_PRODUCT_CAMPAIGN_NAME = 'PDSA Products'
PDSA_CATEGORY_CAMPAIGN_NAME = 'PDSA Categories'
AD_DESCRIPTION_MAX_LENGTH = 90
AD_DESCRIPTION_MIN_LENGTH = 35


class GoogleAdsEditorMgr:

  def __init__(self, config: config_utils.Config):
    self._config = config
    self._headers = [
        CAMP_NAME, CAMP_BUDGET, DSA_WEBSITE, DSA_LANG, DSA_TARGETING_SOURCE,
        DSA_PAGE_FEEDS, ADGROUP_NAME, ADGROUP_MAX_CPM, ADGROUP_TARGET_CPM,
        ADGROUP_TYPE, TARGET_CONDITION, TARGET_VALUE, AD_TYPE,
        AD_DESCRIPTION_ORIG, AD_DESCRIPTION, IMAGE
    ]
    self._rows = []
    self._orig_descriptions = {}

  def __create_row(self):
    ''' Creates an object that represents an empty row of the csv file '''
    row = {}
    for header in self._headers:
      row[header] = ''
    return row

  def __split_to_sentances(self, descrption):
    ''' break a paragraph into sentences and return a list '''
    sentenceEnders = re.compile('[.,!?\|]')
    sentenceList = sentenceEnders.split(descrption)
    return sentenceList

  def __get_ad_description(self, product):
    ''' The limit for description is 90 characters, which can be easily exceeded.
    This method will decide what information to take as the ad description. It also
    removes any commas that exist in the string to avoid messing up the CSV file
    If no valid sentance is found, we will leave it empty to be modified from
    Google Ads Editor
    '''
    # Try to use adcustomizers
    if self._config.ad_description_template:
      # NOTE: inside template we have macros like {field},
      # they should be translated to adcustomizer syntax  {=AD_CUSTOMIZER_FEED.field}
      def replacer(match: re.Match):
        return '{=' + self._config.adcustomizer_feed_name + '.' + match.group(
            1) + '}'

      description = re.sub('\{([^}]+)\}', replacer,
                           self._config.ad_description_template)
      if description != self._config.ad_description_template:
        return description

    if len(product.description) <= AD_DESCRIPTION_MAX_LENGTH:
      return product.description

    if len(product.title) <= AD_DESCRIPTION_MAX_LENGTH:
      return product.title

    # The description and title are too long, split them to sentances
    all_sentences = self.__split_to_sentances(
        product.description) + self.__split_to_sentances(product.title)
    for sentence in all_sentences:
      if (len(sentence) >= AD_DESCRIPTION_MIN_LENGTH and
          len(sentence) <= AD_DESCRIPTION_MAX_LENGTH):
        return sentence
    return ''

  def __get_category_description(self, label):
    desc = self._config.category_ad_descriptions.get(label, None)
    if desc is None:
      raise ValueError(
          f'Mapping for label {label} is missing in configuration (category_ad_descriptions)'
      )
    return desc

  def get_headers(self):
    return self._headers

  def set_original_description(self, orig_desc):
    self._orig_descriptions = orig_desc

  def add_campaign(self, name):
    campaign = self.__create_row()
    campaign_details = {
        CAMP_NAME: name,
        DSA_WEBSITE: self._config.dsa_website,
        DSA_LANG: self._config.dsa_lang or '',
        DSA_TARGETING_SOURCE: 'Page feed',
        DSA_PAGE_FEEDS: self._config.page_feed_name
    }
    campaign.update(campaign_details)
    self._rows.append(campaign)

  def add_adgroup(self, campaign_name: str, adgroup_name: str,
                  is_product_level: bool, product, label: str):
    # Add the ad group row
    adgroup = self.__create_row()

    orig_ad_description = self._orig_descriptions.get(
        (campaign_name, adgroup_name)) or ''
    # TODO: current __get_category_description fails if a mapping (label-category) is missing in config
    ad_description = self.__get_ad_description(
        product) if is_product_level else self.__get_category_description(label)
    adgroup_details = {
        CAMP_NAME: campaign_name,
        ADGROUP_NAME: adgroup_name,
        ADGROUP_MAX_CPM: '0.01',
        ADGROUP_TARGET_CPM: '0.01',
        ADGROUP_TYPE: 'Dynamic',
        TARGET_CONDITION: 'CUSTOM_LABEL',
        TARGET_VALUE: label,
        AD_TYPE: 'Expanded Dynamic Search Ad',
        AD_DESCRIPTION_ORIG: orig_ad_description,
        AD_DESCRIPTION: ad_description.strip()
    }
    adgroup.update(adgroup_details)
    self._rows.append(adgroup)

    # Add the Dynamic targeting row
    dynamic_target = self.__create_row()
    dynamic_target_details = {
        CAMP_NAME: campaign_name,
        ADGROUP_NAME: adgroup_name,
        TARGET_CONDITION: 'CUSTOM_LABEL',
        TARGET_VALUE: label,
    }
    dynamic_target.update(dynamic_target_details)
    self._rows.append(dynamic_target)

    # Add the image extension row
    if product.image_link:
      folder = os.path.join(self._config.output_folder,
                            self._config.image_folder)
      local_image_path = file_utils.download_image(product.image_link, folder)
      rel_image_path = os.path.relpath(local_image_path,
                                       self._config.output_folder or '')
      self.add_image_ext(campaign_name, adgroup_name, rel_image_path)

  def add_image_ext(self, campaign_name: str, adgroup_name: str, img_path: str):
    image = self.__create_row()
    image_details = {
        CAMP_NAME: campaign_name,
        ADGROUP_NAME: adgroup_name,
        IMAGE: img_path
    }
    image.update(image_details)
    self._rows.append(image)

  def generate_csv(self, output_csv_path: str):
    with open(output_csv_path, 'w') as csv_file:
      writer = csv.DictWriter(csv_file, fieldnames=self._headers)
      writer.writeheader()
      writer.writerows(self._rows)


def _get_ads_attribute_type(field, parent_field = None) -> str:
  # https://support.google.com/google-ads/answer/6093368
  # supported attrubute types: text, number, price, date
  field_type = field.field_type
  if field_type == 'STRING':
    return 'text'
  if field_type == 'INTEGER' or field_type == 'NUMERIC':
    if parent_field and 'price' in parent_field.name :
      return 'price'
    return 'number'
  if field_type == 'DATE' or field_type == 'TIMESTAMP':
    return 'date'


def _get_product_adgroup_name(product) -> str:
  return 'Ad group ' + product.offer_id


def _get_subfield_name(field, subfield):
  """Create a field name for adcustomizer from a nested field (field of RECORD)"""
  # NOTE: Google Ads doesn't support "." in field names
  return field.name + '_' + subfield.name


class AdCustomizerGenerator:

  def __init__(self, products) -> None:
    self._adcustomizer_values = []
    self._adcustomizer_columns = []
    self._attr_types_by_name = {}
    self._schema = products.schema
    self._adcustomizer_ignore_columns = [
        'data_date', 'latest_date', 'product_id', 'merchant_id', 'offer_id',
        'link', 'image_link', 'additional_image_links',
        'google_product_category_path', 'product_type', 'unique_product_id',
        'custom_labels', 'pdsa_custom_labels'
    ]
    # initialize columns:
    # ignoring repeated fields(array) and expanding records, also ignoring unsupported types
    for field in products.schema:
      if field.mode == 'REPEATED' or field.name in self._adcustomizer_ignore_columns:
        continue
      elif field.field_type == 'RECORD':
        for subfield in field.fields:
          # prefix subfield with field (e.g. custom_labels.label_0)
          attr_type = _get_ads_attribute_type(subfield, field)
          if not attr_type:
            continue
          field_name = _get_subfield_name(field, subfield)
          self._attr_types_by_name[field_name] = attr_type
          self._adcustomizer_columns.append(field_name + ' (' + attr_type + ')')
      else:
        attr_type = _get_ads_attribute_type(field)
        if not attr_type:
          continue
        self._attr_types_by_name[field.name] = attr_type
        self._adcustomizer_columns.append(field.name + ' (' + attr_type + ')')
    self._adcustomizer_columns.append('Target campaign')
    self._adcustomizer_columns.append('Target ad group')

  def _serialize_value(self, bg_value, field_schema):
    if bg_value is None:
      return ''
    if field_schema.field_type in ['INTEGER', 'NUMERIC']:
      if type(bg_value) is decimal.Decimal:
        # There's a bug in Ad Customizers that doesn't allow float values
        # TODO: remove the casting to int
        return str(int(bg_value))
    bg_value = re.sub('[-|]', '', str(bg_value))
    # NOTE: Google Ads requires fields to be 80 symbols or less (otherwise there will be an error: AD_PLACEHOLDER_STRING_TOO_LONG)
    return re.sub(' +', ' ', bg_value)[:80]

  def _get_price_with_currency(self, price_field, use_symbol = False):
    value = price_field.get('value')
    currency = price_field.get('currency')
    if value is None or currency is None:
      return ''
    if use_symbol:
      currency_codes = CurrencyCodes()
      symbol = currency_codes.get_symbol(currency)
      symbol = (re.sub('[A-Za-z0-9]', '', symbol))
      return symbol + str(value)
    # There's a bug in Ad Customizers that doesn't allow float values
    # TODO: remove the casting to int
    return str(int(value)) +' '+ currency

  def add_product(self, prod, target_campaign: str, target_adgroup: str):
    row_values = []
    for i in range(len(prod)):
      field_schema = self._schema[i]
      if field_schema.mode == 'REPEATED' or field_schema.name in self._adcustomizer_ignore_columns:
        continue
      field_value = prod[i]
      if field_schema.field_type == 'RECORD':
        for subfield in field_schema.fields:
          field_name = _get_subfield_name(field_schema, subfield)
          if field_name in self._attr_types_by_name:
            # NOTE: we expect field_value to be a value of collections.Mapping
            if field_value is None:
              row_values.append('')
            elif 'price' in field_name and subfield.field_type == 'NUMERIC':
              price_str = self._get_price_with_currency(field_value)
              row_values.append(self._serialize_value(price_str, subfield))
            else:
              row_values.append(
                  self._serialize_value(field_value.get(subfield.name, ''),
                                        subfield))
      elif field_schema.name in self._attr_types_by_name:
        row_values.append(self._serialize_value(field_value, field_schema))
    # finally add standard columns 'Target campaign' and 'Target ad group'
    row_values.append(target_campaign)
    row_values.append(target_adgroup)
    self._adcustomizer_values.append(row_values)

  def get_values(self) -> List[List[Any]]:
    return [self._adcustomizer_columns] + self._adcustomizer_values


class CampaignMgr:
  """ Responsible for creating the campaign and ad group structure that targets
  the pagefeed generated from the GMC feed
  """

  def __init__(self, config: config_utils.Config, products, credentials):
    self._config = config
    self._credentials = credentials
    self._products_by_label = {}
    self._create_product_campaign = self._create_category_campaign = False
    self._adcustomizer_gen = AdCustomizerGenerator(products)

    for prod in products:
      custom_labels = prod['pdsa_custom_labels'].split(';')
      product_level_adgroup = False
      for label in custom_labels:
        label = label.strip()
        if is_product_label(label):
          self._create_product_campaign = True
          product_level_adgroup = True
        else:
          self._create_category_campaign = True

        # Only add the product if this custom label wasn't added before
        # i.e. for category labels, take the first product info
        if label not in self._products_by_label:
          self._products_by_label[label] = prod

      # TODO: it's OK for MVP, but in the future we should avoid read all data into the memory
      # read out all columns for adcustomizer feed
      if product_level_adgroup:
        self._adcustomizer_gen.add_product(
            prod, self._config.product_campaign_name or
            PDSA_PRODUCT_CAMPAIGN_NAME, _get_product_adgroup_name(prod))

  def generate_adcustomizers(self, generate_csv: bool):
    values = self._adcustomizer_gen.get_values()
    # generate CSV (for creating)
    if generate_csv:
      output_csv_path = os.path.join(self._config.output_folder,
                                     self._config.adcustomizer_output_file)
      with open(output_csv_path, 'w') as csv_file:
        writer = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(values)
      logging.info(f'Generated adcustomizers data in {output_csv_path} file')

    # generate spreadsheet (for updating)
    sheets_client = sheets_utils.GoogleSpreadsheetUtils(self._credentials)
    sheets_client.update_values(self._config.adcustomizer_spreadsheetid,
                                "A1:AZ", values)
    url = f'https://docs.google.com/spreadsheets/d/{self._config.adcustomizer_spreadsheetid}'
    logging.info('Generated adcustomizers feed in Google Spreadsheet ' + url)

  def generate_csv(self) -> str:
    """Generate a CSV for Google Ads Editor with DSA campaign data"""
    if not self._products_by_label:
      return

    output_csv_path = os.path.join(self._config.output_folder,
                                   self._config.campaign_output_file)
    gae = GoogleAdsEditorMgr(self._config)

    # Before generating the new file, get ad descriptions from the old csv if
    # it exists (If the ad description changes, the old one will be needed)
    csv_file = self._get_previous_data(output_csv_path)
    if not csv_file is None:
      with csv_file:
        reader = csv.DictReader(csv_file, gae.get_headers())
        orig_desc = {
            tuple((row[CAMP_NAME], row[ADGROUP_NAME])): row[AD_DESCRIPTION]
            for row in reader
            if row[AD_DESCRIPTION] != ''
        }
        gae.set_original_description(orig_desc)

    # If the campaign doesn't exist, create an empty one with default settings
    product_campaign_name = self._config.product_campaign_name
    if not product_campaign_name:
      product_campaign_name = PDSA_PRODUCT_CAMPAIGN_NAME
    if self._create_product_campaign:
      gae.add_campaign(product_campaign_name)

    category_campaign_name = self._config.category_campaign_name
    if not category_campaign_name:
      category_campaign_name = PDSA_CATEGORY_CAMPAIGN_NAME
    if self._create_category_campaign:
      gae.add_campaign(category_campaign_name)

    for label in self._products_by_label:
      is_product_level = is_product_label(label)
      campaign_name = product_campaign_name if is_product_level else category_campaign_name
      product = self._products_by_label[label]
      # If it's category level, use the label without 'PDSA_CATEGORY_'
      adgroup_name = _get_product_adgroup_name(
          product) if is_product_level else 'Ad group ' + label
      # NOTE: adgroup name is important as we use it in adcustomizers as well
      gae.add_adgroup(campaign_name, adgroup_name, is_product_level, product,
                      label)

    gae.generate_csv(output_csv_path)
    file_utils.upload_file_to_gcs(self._config.project_id, self._credentials,
                                  output_csv_path)

    return output_csv_path

  def _get_previous_data(self, output_csv_path: str):
    file_name = os.path.basename(output_csv_path)
    bucket = file_utils.get_or_create_project_gcs_bucket(
        self._config.project_id, self._credentials)
    csv_file = None
    blob = bucket.get_blob(file_name)
    if blob:
      csv_file = blob.open()
    else:
      # there's no a previous csv file on GCS, try to reuse a local file
      if os.path.isfile(output_csv_path):
        csv_file = open(output_csv_path, 'r')
      else:
        logging.info('Previous campaign data file wasn\'t found')
    return csv_file


def generate_csv(config: config_utils.Config, products, credentials):
  campaign_mgr = CampaignMgr(config, products, credentials)

  campaign_mgr.generate_adcustomizers(generate_csv=True)

  return campaign_mgr.generate_csv()


def is_product_label(label):
  return label.startswith('product_')
