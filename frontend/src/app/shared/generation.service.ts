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
import { ApiService, GenerateResponse } from './api.service';
import { ConfigService } from './config.service';

export interface GenerateOptions {
  skipDownload?: boolean
};

@Injectable({
  providedIn: 'root'
})
export class GenerationService {
  constructor(private apiService: ApiService, private configService: ConfigService) {
  }

  async generatePageFeed(opts: GenerateOptions = {}): Promise<GenerateResponse> {
    const target = this.configService.currentTarget;
    let res = await this.apiService.generatePageFeed(target);
    if (!opts?.skipDownload)
      await this.apiService.downloadFile(res.filename);
    return res;
  }

  async generateAdcustomizers(opts: GenerateOptions = {}): Promise<GenerateResponse> {
    const target = this.configService.currentTarget;
    let res = await this.apiService.generateAdcustomizers(target);
    if (!opts?.skipDownload)
      await this.apiService.downloadFile(res.filename);
    return res;
  }

  async generateAdCampaign(opts: GenerateOptions = {}): Promise<GenerateResponse> {
    const target = this.configService.currentTarget;
    let res = await this.apiService.generateAdCampaign(target);
    if (!opts?.skipDownload)
      await this.apiService.downloadFile(res.filename);
    return res;
  }
}