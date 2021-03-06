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
"""
Responsible for campaign creation of Product DSAs to upload into Google Ads
Uploading will initially be only supported through Google Ads Editor
i.e. The expected output is a CSV file.
"""
import csv
from io import TextIOWrapper
import re
import os
import decimal
import logging
from datetime import datetime
import concurrent.futures
from urllib import parse
from typing import Any, Dict, List, Tuple
from common import file_utils, image_utils, sheets_utils
from forex_python.converter import CurrencyCodes
from app.context import Context
from common.utils import DiskUsageUnits, get_rss, get_disk_usage

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
  """Component that incapsulates logic for creating CSV with campaign data for Google Ads Editor"""

  def __init__(self, context: Context):
    self._context = context
    self._headers = [
        CAMP_NAME, CAMP_BUDGET, DSA_WEBSITE, DSA_LANG, DSA_TARGETING_SOURCE,
        DSA_PAGE_FEEDS, ADGROUP_NAME, ADGROUP_MAX_CPM, ADGROUP_TARGET_CPM,
        ADGROUP_TYPE, TARGET_CONDITION, TARGET_VALUE, AD_TYPE,
        AD_DESCRIPTION_ORIG, AD_DESCRIPTION, IMAGE
    ]
    self._rows = []
    self._orig_descriptions = {}
    self._re_splitter = re.compile('[.!?|\n]')
    self._re_splitter_full = re.compile('[.!?|\n,;]')

  def __create_row(self):
    ''' Creates an object that represents an empty row of the csv file '''
    row = {}
    for header in self._headers:
      row[header] = ''
    return row

  def __split_to_sentences(self, descrption: str, all_separators: bool):
    ''' Break a paragraph into sentences and return a list '''
    if not descrption:
      return []
    sentenceEnders = self._re_splitter_full if all_separators else self._re_splitter
    sentenceList = sentenceEnders.split(descrption)
    return sentenceList

  def __get_ad_description_from_template(self, product):
    ''' This method tries to generate an ad description using ad customizers template.
        The limit for description is 90 characters.
    '''
    # Try to use adcustomizers
    if self._context.target.ad_description_template:
      # NOTE: inside template we have macros like {field},
      # they should be translated to adcustomizer syntax  {=AD_CUSTOMIZER_FEED.field}
      def replacer(match: re.Match):
        return '{=' + self._context.target.adcustomizer_feed_name + '.' + match.group(
            1) + '}'

      # TODO: an expanded ad description (after evaluating adcustomizers) can exceed the ad description maximum length
      description = self._context.target.ad_description_template
      # support for product_description - static description from configuration
      description = description.replace(
          '{product_description}', self._context.target.product_description)
      description = re.sub('\{([^}]+)\}', replacer, description)
      if description != self._context.target.ad_description_template:
        return description
      return ''

  def __get_ad_description(self, product):
    ''' The limit for description is 90 characters, which can be easily exceeded.
    This method will decide what information to take as the ad description.
    If no valid sentance is found, we will leave it empty to be modified from
    Google Ads Editor
    '''
    if self._context.target.product_description and not self._context.target.product_description_as_fallback_only and len(
        self._context.target.product_description) <= AD_DESCRIPTION_MAX_LENGTH:
      return self._context.target.product_description

    if product.custom_description and len(
        product.custom_description) > 0 and len(
            product.custom_description) <= AD_DESCRIPTION_MAX_LENGTH:
      return product.custom_description

    if product.description and len(
        product.description) <= AD_DESCRIPTION_MAX_LENGTH:
      return product.description

    if product.title and len(product.title) <= AD_DESCRIPTION_MAX_LENGTH:
      return product.title

    if self._context.target.product_description and self._context.target.product_description_as_fallback_only and len(
        self._context.target.product_description) <= AD_DESCRIPTION_MAX_LENGTH:
      return self._context.target.product_description

    # The description and title are too long, split them to sentences
    all_sentences = (self.__split_to_sentences(product.title, False) +
                     self.__split_to_sentences(product.description, False))
    for sentence in all_sentences:
      if (len(sentence) >= AD_DESCRIPTION_MIN_LENGTH and
          len(sentence) <= AD_DESCRIPTION_MAX_LENGTH):
        return sentence
    # this time split using commas and semi-colons
    all_sentences = (self.__split_to_sentences(product.title, True) +
                     self.__split_to_sentences(product.description, True))
    for sentence in all_sentences:
      if (len(sentence) >= AD_DESCRIPTION_MIN_LENGTH and
          len(sentence) <= AD_DESCRIPTION_MAX_LENGTH):
        return sentence
    return ''

  def __get_category_description(self, label):
    desc = None
    if self._context.target.category_ad_descriptions:
      desc = self._context.target.category_ad_descriptions.get(label, None)
    if not desc or desc == '':
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
        DSA_WEBSITE: self._context.target.dsa_website,
        DSA_LANG: self._context.target.dsa_lang or '',
        DSA_TARGETING_SOURCE: 'Page feed',
        DSA_PAGE_FEEDS: self._context.target.page_feed_name
    }
    campaign.update(campaign_details)
    self._rows.append(campaign)

  def add_adgroup(self, campaign_name: str, adgroup_name: str,
                  is_product_level: bool, product, label: str,
                  images: List[str]):

    orig_ad_description = self._orig_descriptions.get(
        (campaign_name, adgroup_name)) or ''
    if is_product_level:
      # Add the ad group row if we have adcustomizers
      ad_description_from_template = self.__get_ad_description_from_template(
          product)
      if ad_description_from_template:
        adgroup = self.__create_row()
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
            AD_DESCRIPTION: ad_description_from_template.strip()
        }
        adgroup.update(adgroup_details)
        self._rows.append(adgroup)

    # Add the ad group row (with default description)
    adgroup = self.__create_row()
    # TODO: currently __get_category_description raises ValueError if a mapping (label-category) is missing in config
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

    # Add the image extension row(s)
    if images:
      for local_image_path in images:
        self.add_image_ext(campaign_name, adgroup_name, local_image_path)

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
    self._context.ensure_folders()
    # NOTE: Google Ads Editor doesn't understand UTF-8!
    with open(output_csv_path, 'w', encoding='UTF-16') as csv_file:
      writer = csv.DictWriter(csv_file, fieldnames=self._headers)
      writer.writeheader()
      writer.writerows(self._rows)


def _get_ads_attribute_type(field, parent_field=None) -> str:
  # https://support.google.com/google-ads/answer/6093368
  # supported attrubute types: text, number, price, date
  field_type = field.field_type
  if field_type == 'STRING':
    return 'text'
  if field_type == 'INTEGER' or field_type == 'NUMERIC':
    if parent_field and 'price' in parent_field.name:
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
        'pdsa_custom_labels'
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

  def _serialize_value(self, bq_value, field_schema):
    if bq_value is None:
      return ''
    if field_schema.field_type in ['INTEGER', 'NUMERIC']:
      if type(bq_value) is decimal.Decimal:
        # There's a bug in Ad Customizers that doesn't allow float values
        # TODO: remove the casting to int
        return str(int(bq_value))
    bq_value = re.sub('[-|]', '', str(bq_value))
    # NOTE: Google Ads requires fields to be 80 symbols or less (otherwise there will be an error: AD_PLACEHOLDER_STRING_TOO_LONG)
    return re.sub(' +', ' ', bq_value)[:80]

  def _get_price_with_currency(self, price_field, use_symbol=False):
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
    return str(int(value)) + ' ' + currency

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

  def __init__(self, context: Context, products):
    self._context = context
    self._credentials = context.credentials
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

      # TODO: it's OK for MVP, but in the future we should avoid read all data into the memory.
      # read out all columns for adcustomizer feed
      if product_level_adgroup:
        self._adcustomizer_gen.add_product(
            prod, context.target.product_campaign_name or
            PDSA_PRODUCT_CAMPAIGN_NAME, _get_product_adgroup_name(prod))

  def generate_adcustomizers(self, generate_csv: bool) -> str:
    logging.info('Starting generating adcustomizer feed')
    values = self._adcustomizer_gen.get_values()
    # generate CSV (for creating)
    output_csv_path = None
    if generate_csv:
      self._context.ensure_folders()
      output_csv_path = os.path.join(
          self._context.output_folder,
          self._context.target.adcustomizer_output_file)
      with open(output_csv_path, 'w') as csv_file:
        writer = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(values)
      logging.info(f'Generated adcustomizers data in {output_csv_path} file')

    # generate spreadsheet (for updating)
    sheets_client = sheets_utils.GoogleSpreadsheetUtils(self._credentials)
    sheets_client.update_values(self._context.target.adcustomizer_spreadsheetid,
                                "A1:AZ", values)
    url = f'https://docs.google.com/spreadsheets/d/{self._context.target.adcustomizer_spreadsheetid}'
    logging.info('Generated adcustomizers feed in Google Spreadsheet ' + url)
    return output_csv_path

  def generate_csv(self) -> str:
    """Generate a CSV for Google Ads Editor with DSA campaign data"""
    if not self._products_by_label:
      return
    old_rss = get_rss()
    total, used, free = get_disk_usage(DiskUsageUnits.MB)

    logging.info(f'Starting generating campaign data (/tmp: total={total}, used={used})')
    output_csv_path = os.path.join(self._context.output_folder,
                                   self._context.target.campaign_output_file)
    gae = GoogleAdsEditorMgr(self._context)

    # Before generating the new file, get ad descriptions from the old csv if
    # it exists (If the ad description changes, the old one will be needed)
    csv_file = self._get_previous_data(output_csv_path)
    if not csv_file is None:
      with csv_file:
        try:
          reader = csv.DictReader(csv_file, gae.get_headers())
          orig_desc = {
              tuple((row[CAMP_NAME], row[ADGROUP_NAME])): row[AD_DESCRIPTION]
              for row in reader
              if row[AD_DESCRIPTION] != ''
          }
          gae.set_original_description(orig_desc)
        except UnicodeError as e:
          logging.info(
              f'Failed to read CSV with previous data because of encoding mismatch: {e}'
          )
          # ignore encoding mismatch

    # If the campaign doesn't exist, create an empty one with default settings
    product_campaign_name = self._context.target.product_campaign_name
    if not product_campaign_name:
      product_campaign_name = PDSA_PRODUCT_CAMPAIGN_NAME
    if self._create_product_campaign:
      gae.add_campaign(product_campaign_name)

    category_campaign_name = self._context.target.category_campaign_name
    if not category_campaign_name:
      category_campaign_name = PDSA_CATEGORY_CAMPAIGN_NAME
    if self._create_category_campaign:
      gae.add_campaign(category_campaign_name)

    max_image_dimension = self._context.target.max_image_dimension
    if max_image_dimension is None:
      max_image_dimension = 0
    else:
      max_image_dimension = int(max_image_dimension)
    logging.info(
        f'[CampaignMgr] Using max_image_dimension: {max_image_dimension}')
    if self._context.images_dry_run:
      logging.warning(
          f'[CampaignMgr] using images_dry_run mode (images won\'t be downloaded and processed)'
      )
    gcs_files_metadata = {
    }  # a map from file name to datetime of last-modified timestamp
    if self._context.images_on_gcs and not self._context.images_dry_run:
      # fetch all blobs for images on GCS to optimize downloading
      gcs_files_metadata1 = file_utils.get_blobs_metadata(
          self._context.gs_download_path, self._context.storage_client)
      gcs_files_metadata2 = file_utils.get_blobs_metadata(
          self._context.gs_images_path, self._context.storage_client)
      gcs_files_metadata = {
          **gcs_files_metadata1,
          **gcs_files_metadata2
      }  # In 3.9 it can be changed to z=x|y
    self._context.target.init_image_filter()

    i = 0
    for label in self._products_by_label:
      i += 1
      is_product_level = is_product_label(label)
      campaign_name = product_campaign_name if is_product_level else category_campaign_name
      product = self._products_by_label[label]
      # If it's category level, use the label without 'PDSA_CATEGORY_'
      adgroup_name = _get_product_adgroup_name(
          product) if is_product_level else 'Ad group ' + label
      # NOTE: adgroup name is important as we use it in adcustomizers as well
      images = self._get_images(product, max_image_dimension,
                                gcs_files_metadata)
      gae.add_adgroup(campaign_name, adgroup_name, is_product_level, product,
                      label, images)

      max_rss = get_rss()
      logging.info(f'{i:3d} - {label}, images: {len(images)}, mem: {max_rss:,}')
      if max_rss > old_rss:
        logging.info(
            f'RSS increased to {max_rss:,} from {old_rss:,} after processing {images}'
        )
        old_rss = max_rss
      if i % 100 == 0:
        total, used, free = get_disk_usage(DiskUsageUnits.MB)
        logging.info(
            f'Temp partition usage: total={total}, used={used})'
        )

    if self._context.images_on_gcs and not self._context.images_dry_run:
      # remove files on GCS that weren't used by products
      file_utils.gcs_delete_folder_files(
          lambda blob: gcs_files_metadata.get(os.path.basename(blob.name)) !=
          True, self._context.gs_download_path, self._context.storage_client)
      file_utils.gcs_delete_folder_files(
          lambda blob: gcs_files_metadata.get(os.path.basename(blob.name)) !=
          True, self._context.gs_images_path, self._context.storage_client)

    logging.debug('Writing campaign data CSV')
    gae.generate_csv(output_csv_path)
    logging.info(f'Campaign data CSV created in {output_csv_path}')
    if self._context.gcs_bucket:
      gcs_path = file_utils.upload_file_to_gcs(
          output_csv_path,
          self._context.gs_base_path,
          storage_client=self._context.storage_client)
      logging.debug(f'Campaign data CSV uploaded to GCS ({gcs_path})')
    return output_csv_path

  def _generate_filepath_for_image_url(self, uri, folder, product_id):
    parsed_uri = parse.urlparse(uri)
    file_name = os.path.basename(parsed_uri.path)
    local_path = os.path.join(folder, f'{product_id}_{file_name}')
    return local_path

  def _filter_images(self, filters: List[Tuple[bool, re.Pattern]],
                     product_images: List[str]):
    result = []
    for url in product_images:
      include = True
      for negative, pattern in filters:
        if negative:
          include = not pattern.match(url)
          if not include:
            # break to avoid it getting overriden by the next filter
            break
        # if not negative:
        #   include = pattern.match(url)
      if include:
        result.append(url)
    return result

  def _get_images(self, product, max_image_dimension: int,
                  files_metadata: Dict[str, datetime]) -> List[str]:
    """Download all product images, resize them and return a list of local relative paths"""
    download_folder = os.path.join(self._context.output_folder,
                                   self._context.image_folder + '-download')
    image_rel_paths = []
    product_images = []
    if product.image_link:
      product_images.append(product.image_link)
    if product.additional_image_links and not self._context.target.skip_additional_images:
      product_images += product.additional_image_links
    # remove url duplicates from image list
    product_images = list(dict.fromkeys(product_images))
    if self._context.target.image_filter_re:
      product_images = self._filter_images(self._context.target.image_filter_re, product_images)
    # generate a map of urls to local file names
    product_images_to_urls = {
        self._generate_filepath_for_image_url(uri, download_folder,
                                              product.offer_id): uri
        for uri in product_images
    }
    # limit max number of images
    if self._context.target.max_image_count and self._context.target.max_image_count > 0:
      product_images = product_images[:self._context.target.max_image_count]
    logging.debug(product_images)

    dry_run = self._context.images_dry_run
    ts_start = datetime.now()
    # now product_images is a list of product images' urls, let's download them
    os.makedirs(download_folder, exist_ok=True)
    if len(product_images_to_urls) == 0:
      return image_rel_paths
    if len(product_images_to_urls) == 1:
      # no need for parallelization if only one image
      item = list(product_images_to_urls.items())[0]
      product_images = [
          file_utils.download_file(item[1],
                                   item[0],
                                   dry_run=dry_run or files_metadata.get(
                                       os.path.basename(item[0])) == True,
                                   lastModified=files_metadata.get(
                                       os.path.basename(item[0])))
      ]
    else:
      # download all images in parallel
      with concurrent.futures.ThreadPoolExecutor() as exector:
        product_images = exector.map(
            lambda item: file_utils.download_file(
                item[1],
                item[0],
                # NOTE: we use files_metadata as output as well replacing datetime with True for processed files
                # so a file can be encountered a second time, in such a case we'll ignore it
                dry_run=dry_run or files_metadata.get(os.path.basename(item[0])) == True,
                lastModified=files_metadata.get(os.path.basename(item[0]))),
            product_images_to_urls.items())

    elapsed = datetime.now() - ts_start
    logging.debug(f'Images downloaded, elapsed {elapsed}')
    output_folder = os.path.join(self._context.output_folder,
                                 self._context.image_folder)
    # now product_images is a list (iterable) of product images' local file paths
    # for each image we'll create two: square and landscape
    for local_image_path, status in product_images:
      # NOTE: status is either 200 (file was downloaded) or 304 (cache hit),
      # in the latter case we don't have a local copy, so we can't resize and
      # update to gcs, so we assume that there're proper files on gcs already
      # But to be sure we're checking it via files_metadata dictionary - it should contain both "_sq" and "_ls" files;
      # If any of them is missing then optimization (of skipping downloading) disabled.
      dry_run_ = dry_run or self._context.images_on_gcs and status == 304
      if not dry_run and self._context.images_on_gcs and status == 304:
        if not files_metadata.get(file_utils.generate_filename(local_image_path, suffix='_sq')) or \
           not files_metadata.get(file_utils.generate_filename(local_image_path, suffix='_ls')):
          dry_run_ = False
      two_image_file_paths = image_utils.resize(local_image_path,
                                                output_folder,
                                                max_image_dimension,
                                                dry_run=dry_run_)
      if self._context.images_on_gcs:
        if status == 200:
          # we have three image files (original in -download, and two sq_/ls_ in images), upload them to GCS
          file_utils.upload_file_to_gcs(
              local_image_path,
              self._context.gs_download_path,
              storage_client=self._context.storage_client)
          file_utils.upload_file_to_gcs(
              two_image_file_paths[0],
              self._context.gs_images_path,
              storage_client=self._context.storage_client)
          file_utils.upload_file_to_gcs(
              two_image_file_paths[1],
              self._context.gs_images_path,
              storage_client=self._context.storage_client)
        if os.path.exists(local_image_path):
          os.remove(local_image_path)
        if os.path.exists(two_image_file_paths[0]):
          os.remove(two_image_file_paths[0])
        if os.path.exists(two_image_file_paths[1]):
          os.remove(two_image_file_paths[1])

      # NOTE: mark files as used, it'll be used later to remove unneeded files on GCS
      files_metadata[os.path.basename(local_image_path)] = True
      files_metadata[os.path.basename(two_image_file_paths[0])] = True
      files_metadata[os.path.basename(two_image_file_paths[1])] = True
      # Add square image
      rel_image_path_square = os.path.relpath(two_image_file_paths[0],
                                              self._context.output_folder or '')
      image_rel_paths.append(rel_image_path_square)
      # Add landscape
      rel_image_path_landscape = os.path.relpath(
          two_image_file_paths[1], self._context.output_folder or '')
      image_rel_paths.append(rel_image_path_landscape)
    return image_rel_paths

  def _get_previous_data(self, output_csv_path: str) -> TextIOWrapper:
    file_name = os.path.basename(output_csv_path)
    csv_file = None
    blob = None
    if self._context.gcs_bucket:
      result = parse.urlparse(self._context.gs_base_path)
      bucket = file_utils.get_gcs_bucket(
          self._context.gcs_bucket, storage_client=self._context.storage_client)
      if bucket:
        blob = bucket.get_blob(result.path[1:] + '/' + file_name)
    if blob:
      csv_file = blob.open(encoding='UTF-16')
      logging.info(f'Found previous campaign data file on GCS: {file_name}')
    else:
      # there's no a previous csv file on GCS, try to reuse a local file
      if os.path.isfile(output_csv_path):
        csv_file = open(output_csv_path, 'r', encoding='UTF-16')
        logging.info(f'Found previous campaign data file: {output_csv_path}')
      else:
        logging.info('Previous campaign data file wasn\'t found')
    return csv_file


def generate_csv(context: Context, products):
  campaign_mgr = CampaignMgr(context, products)

  campaign_mgr.generate_adcustomizers(generate_csv=True)

  return campaign_mgr.generate_csv()


def is_product_label(label):
  return label.startswith('product_')
