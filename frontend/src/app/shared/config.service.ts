import {Injectable} from '@angular/core';
import {ApiService} from './api.service';

export interface Configuration {
  config_file: string;
  commit_link: string;
  config: any;
  errors: any[];
}
@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  config: Configuration | undefined;

  constructor(public apiService: ApiService) { }

  getConfig(): Configuration | undefined {
    return this.config;
  }

  async loadConfig(): Promise<Configuration> {
    this.config = await this.apiService.getConfig();
    return this.config!;
  }

  async updateConfig(config: any) {
    await this.apiService.updateConfig(config);
  }
}
