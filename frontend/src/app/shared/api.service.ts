/**
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { Injectable } from '@angular/core';
import { BackendService } from './backend.service';

/**
 * Server response type of controllers for generting feeds (page feed and ad customizer feed).
 */
export interface GenerateResponse {
  filename: string,
  spreadsheet_id: string,
  feed_name: string
};

@Injectable({
  providedIn: 'root'
})
export class ApiService {

  constructor(public backendService: BackendService) { }

  async generatePageFeed(target: string|undefined): Promise<GenerateResponse> {
    let res = await this.backendService.getApi<GenerateResponse>(
      '/pagefeed/generate', {target});
    return res;
  }

  async generateAdcustomizers(target: string | undefined): Promise<GenerateResponse> {
    let res = await this.backendService.getApi<GenerateResponse>(
      '/adcustomizers/generate', {target});
    return res;
  }

  async generateAdCampaign(target: string | undefined): Promise<GenerateResponse> {
    let res = await this.backendService.getApi<GenerateResponse>(
      '/campaign/generate', {target});
    return res;
  }

  getLabels(target: string): Promise<Record<string, any>[]> {
    return this.backendService.getApi<Record<string, any>[]>('/labels', { target });
  }

  getProducts(target: string): Promise<Record<string, any>[]> {
    return this.backendService.getApi<Record<string, any>[]>('/products', { target });
  }

  async downloadFile(filename: string): Promise<void> {
    this.backendService.getFile(`/download`, {
      filename: filename
    });
  }

  async getConfig(): Promise<any> {
    return await this.backendService.getApi<any>('/config')
  }

  async updateConfig(config: any): Promise<any> {
    return await this.backendService.postApi('/config', config /*, { emptyResponse: true}*/);
  }
}
