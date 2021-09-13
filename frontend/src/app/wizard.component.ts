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
import { Component, OnInit } from '@angular/core';
import { Form, FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ComponentBase } from './components/component-base';
import { ApiService } from './shared/api.service';

@Component({
  templateUrl: './wizard.component.html',
  styleUrls: ['./wizard.component.scss']
})
export class WizardComponent extends ComponentBase implements OnInit {
  loading: boolean = false;
  pagefeed_speadsheet: string = '';
  adcustomizer_speadsheet: string = ''
  form: FormGroup;

  constructor(private fb: FormBuilder,
    private apiService: ApiService,
    dialog: MatDialog,
    snackBar: MatSnackBar) {
    super(dialog, snackBar);
    this.form = fb.group({
      pagefeed_file: ''
    });
  }

  ngOnInit(): void {
  }

  async generatePageFeed() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.apiService.generatePageFeed();
      this.pagefeed_speadsheet = res.spreadsheet_id;
      //this.form.controls['pagefeed_output_file'].setValue(res.filename);
    } catch (e) {
      this.handleApiError(`Page feed failed to generate`, e);
    } finally {
      this.loading = false;
    }
  }

  async generateAdcustomizers() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.apiService.generateAdcustomizers();
      this.adcustomizer_speadsheet = res.spreadsheet_id;
      //this.form.controls['adcustomizer_output_file'].setValue(res.filename);
    } catch (e) {
      this.handleApiError(`Page feed failed to generate`, e);
    } finally {
      this.loading = false;
    }
  }

  async generateAdCampaign() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.apiService.generateAdCampaign();
    } catch (e) {
      this.handleApiError(`Page feed failed to generate`, e);
    } finally {
      this.loading = false;
    }
  }
}
