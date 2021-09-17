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

interface GenerateOptions {
  skipDownload?: boolean
};
type GenerateResponse = { filename: string, spreadsheet_id: string };

@Injectable({
  providedIn: 'root'
})
export class ApiService {

  constructor(public backendService: BackendService) { }

  async generatePageFeed(opts: GenerateOptions = {}): Promise<GenerateResponse> {
    let res = await this.backendService.getApi<GenerateResponse>(
      '/pagefeed/generate');
    if (!opts?.skipDownload)
      await this.downloadFile(res.filename);
    return res;
  }

  async generateAdcustomizers(opts: GenerateOptions = {}): Promise<GenerateResponse> {
    let res = await this.backendService.getApi<GenerateResponse>(
      '/adcustomizers/generate');
    if (!opts?.skipDownload)
      await this.downloadFile(res.filename);
    return res;
  }

  async generateAdCampaign(opts: GenerateOptions = {}): Promise<GenerateResponse> {
    let res = await this.backendService.getApi<GenerateResponse>(
      '/campaign/generate');
    if (!opts?.skipDownload)
      await this.downloadFile(res.filename);
    return res;
  }

  getLabels(): Promise<Record<string, any>[]> {
    return this.backendService.getApi<Record<string, any>[]>('/labels');
  }

  getProducts(): Promise<Record<string, any>[]> {
    return this.backendService.getApi<Record<string, any>[]>('/products');
  }

  async downloadFile(filename: string): Promise<void> {
    this.backendService.getFile(`/download`, {
      filename: filename
    });
  }

  async getConfig(): Promise<any> {
    return await this.backendService.getApi<any>('/config')
  }

  async updateConfig(config: any): Promise<void> {
    await this.backendService.postApi('/config', config, { emptyResponse: true});
  }
}
