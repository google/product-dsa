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
import csv
from common import config_utils

# Google Ads Editor header names
CAMP_NAME = 'Campaign'
CAMP_BUDGET=	'Budget'
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
AD_DESCRIPTION = 'Description Line 1'

# Default campaign names to use
PDSA_PRODUCT_CAMPAIGN_NAME = 'PDSA Products'
PDSA_CATEGORY_CAMPAIGN_NAME = 'PDSA Categories'

class GoogleAdsEditorMgr:
  def __init__(self, config: config_utils.Config):
    self._config = config
    self._headers = [CAMP_NAME, CAMP_BUDGET, DSA_WEBSITE, DSA_LANG,
      DSA_TARGETING_SOURCE, DSA_PAGE_FEEDS, ADGROUP_NAME, ADGROUP_MAX_CPM,
      ADGROUP_TARGET_CPM, ADGROUP_TYPE, TARGET_CONDITION, TARGET_VALUE,
      AD_TYPE, AD_DESCRIPTION]
    self._rows = []

  def __create_row(self):
    row = {}
    for header in self._headers:
      row[header] = ''
    return row

  def add_campaign(self, name):
    campaign = self.__create_row()
    campaign_details = {
      CAMP_NAME : name,
      DSA_WEBSITE : self._config.dsa_website or '',
      DSA_LANG : self._config.dsa_lang or '',
      DSA_TARGETING_SOURCE: 'Page feed',
      DSA_PAGE_FEEDS: self._config.page_feed_name or 'PDSA_Pagefeed'
    }
    campaign.update(campaign_details)
    self._rows.append(campaign)

  def add_adgroup(self, campaign_name, is_product_level, product, label):
    adgroup = self.__create_row()
    adgroup_details = {
      CAMP_NAME : campaign_name,
      ADGROUP_NAME : 'Ad group ' + product.title,
      ADGROUP_MAX_CPM : '0.01',
      ADGROUP_TARGET_CPM : '0.01',
      ADGROUP_TYPE : 'Dynamic',
      TARGET_CONDITION : 'CUSTOM_LABEL',
      TARGET_VALUE : label,
      AD_TYPE : 'Expanded Dynamic Search Ad',
      AD_DESCRIPTION : product.description if is_product_level else ''
    }
    adgroup.update(adgroup_details)
    self._rows.append(adgroup)

  def generate_csv(self):
    with open('gae-campaigns.csv', 'w') as csv_file:
      writer = csv.DictWriter(csv_file, fieldnames=self._headers)
      writer.writeheader()
      writer.writerows(self._rows)


class CampaignMgr:
  """ Responsible for creating the campaign and ad group structure that targets
  the pagefeed generated from the GMC feed
  """
  def __init__(self, config: config_utils.Config, products):
    self._all_products = products
    self._config = config
    self._custom_labels = {}
    self._create_product_campaign = self._create_category_campaign = False

    for prod in self._all_products:
      custom_labels = prod['pdsa_custom_labels'].split(';')

      for label in custom_labels:
        if is_product_label(label.strip()):
          self._create_product_campaign = True
        else:
          self._create_category_campaign = True

        # Only add the product if this custom label wasn't added before
        # i.e. for category labels, take the first product info
        if label not in self._custom_labels:
          self._custom_labels[label] = prod

  def generate_csv(self):
    if not self._custom_labels:
      return

    gae = GoogleAdsEditorMgr(self._config)
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

    for label in self._custom_labels:
      is_product_level = is_product_label(label)
      campaign_name = product_campaign_name if is_product_level else category_campaign_name
      gae.add_adgroup(campaign_name, is_product_level, self._custom_labels[label], label)

    gae.generate_csv()


def generate_csv(config: config_utils.Config, products):
  campaign_mgr = CampaignMgr( config, products)
  return campaign_mgr.generate_csv()

def is_product_label(label):
    return label.startswith('product_')
