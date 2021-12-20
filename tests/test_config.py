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
import argparse
import os
import pytest
import json
from common import config_utils


def deploy_config(cfg_json, tmpdir):
  config_path = os.path.join(tmpdir, 'config.json')
  with open(config_path, 'w') as f:
    json.dump(cfg_json, f)
  args = argparse.Namespace(config=config_path)
  config = config_utils.get_config(args)
  return config


def test_config_non_existing_should_throw(tmpdir):
  args = argparse.Namespace(
      config=os.path.join(tmpdir, 'non-existing-config.json'))
  with pytest.raises(FileNotFoundError):
    config_utils.get_config(args)


def test_config_with_one_unnamed_target(tmpdir):
  config = deploy_config({"targets": [{}]}, tmpdir)
  assert config.targets[0].name == "default"


def test_config_parse_empty(tmpdir):
  config = deploy_config({}, tmpdir)
  errors = config.validate()
  assert len(errors) > 1
  assert config.pubsub_topic_dt_finish == config_utils.Config.pubsub_topic_dt_finish


def test_config_parse(tmpdir):
  config = deploy_config(
      {
          "project_id": "project1",
          "merchant_id": "root",
          "dataset_id": "ds1",
          "dataset_location": "europe",
          "dt_schedule": "every 6 hours",
          "targets": [{
              "name": "target1",
              "merchant_id": "child",
              "dsa_website": "www.example.com"
          }, {}]
      }, tmpdir)
  assert config.merchant_id == 'root'
  assert config.project_id == 'project1'
  assert config.dataset_id == 'ds1'
  assert config.dataset_location == 'europe'
  assert config.dt_schedule == 'every 6 hours'
  assert len(config.targets) == 2
  target: config_utils.ConfigTarget = config.targets[0]
  assert target.name == "target1"
  assert target.merchant_id == "child"
  assert target.dsa_website == "www.example.com"
  target = config.targets[1]
  assert target.name == ""
  assert target.merchant_id == ""
  assert target.ad_description_template == config_utils.ConfigTarget.ad_description_template
  assert target.adcustomizer_feed_name == config_utils.ConfigTarget.adcustomizer_feed_name
  assert target.adcustomizer_output_file == config_utils.ConfigTarget.adcustomizer_output_file
  assert target.adcustomizer_spreadsheetid == ""
  assert target.ads_customer_id == ""
  assert target.campaign_output_file == config_utils.ConfigTarget.campaign_output_file
  #assert target.category_ad_descriptions
  assert target.category_campaign_name == ""
  assert target.dsa_lang == config_utils.ConfigTarget.dsa_lang
  assert target.dsa_website == ""
  assert target.page_feed_name == config_utils.ConfigTarget.page_feed_name
  assert target.page_feed_output_file == config_utils.ConfigTarget.page_feed_output_file
  assert target.page_feed_spreadsheetid == ""
  assert target.product_campaign_name == ""


def test_save_config(tmpdir):
  config = config_utils.Config()
  config.merchant_id = 1
  config.dataset_id = "ds1"
  config.dt_schedule = "daily"
  config.targets.append(config_utils.ConfigTarget())
  config.targets[0].ad_description_template = "template"
  config.targets[0].dsa_website = "example.com"
  config_path = os.path.join(tmpdir, 'config_new.json')
  config_utils.save_config(config, config_path)
  args = argparse.Namespace(config=config_path)
  config_new = config_utils.get_config(args)
  assert config.dataset_id == config_new.dataset_id
  assert config.dataset_location == config_new.dataset_location
  assert config.dt_schedule == config_new.dt_schedule
  assert config.pubsub_topic_dt_finish == config_new.pubsub_topic_dt_finish


def test_validate_target_name():
  target = config_utils.ConfigTarget()
  assert target.validate()[0]['field'] == 'name'
  target.name = " "
  assert target.validate()[0]['field'] == 'name'
  target.name = " abc "
  assert target.validate()[0]['field'] == 'name'
  target.name = "#name"
  assert target.validate()[0]['field'] == 'name'
  target.name = "ABC-abc_01234567890"
  assert len(target.validate()) == 0