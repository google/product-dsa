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
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ComponentBase } from './components/component-base';
import { ApiService } from './shared/api.service';
import { ConfigService } from './shared/config.service';

@Component({
  templateUrl: './config.component.html',
  styleUrls: ['./config.component.scss']
})
export class ConfigComponent extends ComponentBase implements OnInit {
  loading: boolean = false;
  form: FormGroup;

  constructor(private fb: FormBuilder,
    private configService: ConfigService,
    dialog: MatDialog,
    snackBar: MatSnackBar) {
    super(dialog, snackBar);
    this.form = fb.group({
      configfile: '',
      project_id: '',
      merchant_id: '',
      dataset_id: '',
      dataset_location: '',
      page_feed_name: '',
      page_feed_spreadsheetid: '',
      adcustomizer_feed_name: '',
      adcustomizer_spreadsheetid: '',
      ad_description_template: '',
      dsa_lang: '',
      dsa_website: '',
      // "dt_schedule":

      config: {}
    });
  }

  async ngOnInit() {
    try {
      this.loading = true;
      let cfg = this.configService.getConfig();
      if (!cfg)
        cfg = await this.configService.loadConfig();
      this.form.controls['configfile'].setValue(cfg.configfile);
      for (let field of Object.keys(cfg.config)) {
        let control = this.form.controls[field];
        if (control) {
          control.setValue(cfg.config[field]);
        }
      }
    } catch (e) {
      this.handleApiError(`An error occured during fetching configuration`, e);
    } finally {
      this.loading = false;
    }
  }

}
