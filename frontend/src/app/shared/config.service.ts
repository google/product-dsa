import {Injectable} from '@angular/core';
import { BehaviorSubject } from 'rxjs';
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

  loaded: BehaviorSubject<any> = new BehaviorSubject<any>(null);
  currentTarget: string|undefined;

  getConfig(): Configuration | undefined {
    return this.config;
  }

  async loadConfig(): Promise<Configuration> {
    this.config = await this.apiService.getConfig();
    this.loaded.next(this.config?.config);
    return this.config!;
  }

  async updateConfig(config: any) {
    this.loaded.next(config);
    await this.apiService.updateConfig(config);
  }
}
