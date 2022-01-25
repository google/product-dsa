/**
 * Copyright 2022 Google LLC
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
import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { GenerationComponentBase } from './components/generation-component-base';
import { GenerationService } from './shared/generation.service';
import { NotificatinService } from './shared/notification.service';

@Component({
  templateUrl: './wizard.component.html',
  styleUrls: ['./wizard.component.scss']
})
export class WizardComponent extends GenerationComponentBase implements OnInit {
  loading: boolean = false;
  pagefeed_speadsheet: string = '';
  pagefeed_name: string = '';
  adcustomizer_speadsheet: string = ''
  adcustomizer_feed_name: string = ''
  form: FormGroup;

  constructor(fb: FormBuilder,
    generationService: GenerationService,
    notificationSvc: NotificatinService) {
    super(generationService, notificationSvc);
    this.form = fb.group({
      images_dry_run: false
    });
  }

  ngOnInit(): void {
  }

  async generatePageFeed() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.generationService.generatePageFeed();
      this.pagefeed_speadsheet = res.spreadsheet_id;
      this.pagefeed_name = res.feed_name;
    } catch (e) {
      this.handleApiError(`A failure occured`, e);
    } finally {
      this.loading = false;
    }
  }

  async generateAdcustomizers() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.generationService.generateAdcustomizers();
      this.adcustomizer_speadsheet = res.spreadsheet_id;
      this.adcustomizer_feed_name = res.feed_name;
    } catch (e) {
      this.handleApiError(`A failure occured`, e);
    } finally {
      this.loading = false;
    }
  }
}
