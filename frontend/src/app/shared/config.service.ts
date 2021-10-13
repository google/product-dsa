import {Injectable} from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import {ApiService} from './api.service';

export interface ConfigurationTarget {
  name: string;
  merchant_id: string;
  //ads_customer_id: string;
  product_campaign_name: string;
  category_campaign_name: string;
  dsa_website: string;
  dsa_lang: string;
  page_feed_name: string;
  page_feed_spreadsheetid: string;
  adcustomizer_feed_name: string;
  adcustomizer_spreadsheetid: string;
  //page_feed_output_file: string;
  //campaign_output_file: string;
  //adcustomizer_output_file: string;
  ad_description_template: string;
  category_ad_descriptions: any;  // TODO
}
export type TargetNames = keyof ConfigurationTarget;
export interface Configuration {
  // GCP project id
  project_id: string;
  // dataset id in BigQuery for GMC - BQ data transfer
  dataset_id: string;
  // location for dataset in BigQuery
  dataset_location: string;
  // GMC merchant id
  merchant_id: string;
  // DataTransfer schedule(syntax - https://cloud.google.com/appengine/docs/flexible/python/scheduling-jobs-with-cron-yaml#cron_yaml_The_schedule_format)
  // if empty default scheduling will be used - run DT daily.E.g. 'every 6 hours'
  dt_schedule: string;
  // pub / sub topic id for publishing message on GMC Data Transfer completions
  pubsub_topic_dt_finish: string;
  // targets
  targets: ConfigurationTarget[];
}
export interface ConfigError {
  error: string;
  field: string;
}
export interface GetConfigResponse {
  config_file: string;
  commit_link: string;
  config: Configuration;
  errors?: ConfigError[];
}
@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  config: GetConfigResponse | undefined;

  constructor(public apiService: ApiService) { }

  loaded: BehaviorSubject<any> = new BehaviorSubject<any>(null);
  currentTarget: string|undefined;

  getConfig(): GetConfigResponse | undefined {
    return this.config;
  }

  async loadConfig(): Promise<GetConfigResponse> {
    this.config = await this.apiService.getConfig();
    this.loaded.next(this.config?.config);
    return this.config!;
  }

  async updateConfig(config: any): Promise<{ errors?: ConfigError[] }> {
    let res = await this.apiService.updateConfig(config);
    this.loaded.next(config);
    return res;
  }
}
