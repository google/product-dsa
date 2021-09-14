import { Injectable } from '@angular/core';
import { ApiService } from './api.service';

export interface Configuration {
  configfile: string;
  config: any;
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

  updateConfig() {
    // TODO
  }
}