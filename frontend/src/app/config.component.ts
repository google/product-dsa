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
import {Component, OnInit} from '@angular/core';
import {FormBuilder, FormGroup} from '@angular/forms';
import {MatDialog} from '@angular/material/dialog';
import {MatSnackBar} from '@angular/material/snack-bar';
import {ComponentBase} from './components/component-base';
import {ApiService} from './shared/api.service';
import {ConfigService, Configuration} from './shared/config.service';

@Component({
  templateUrl: './config.component.html',
  styleUrls: ['./config.component.scss']
})
export class ConfigComponent extends ComponentBase implements OnInit {
  loading: boolean = false;
  form: FormGroup;
  config_file: string | undefined;
  commit_link: string | undefined;
  editable = false;

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
      dt_schedule: ''
    });
  }

  async ngOnInit() {
    try {
      this.loading = true;
      let cfg = this.configService.getConfig();
      if (!cfg)
        cfg = await this.configService.loadConfig();
      this.updateConfig(cfg);
      if (cfg.errors.length) {
        // Handle the errors here
        let errors: any = {error: ''};
        for (var msg of cfg.errors) {
          errors.error += (msg['field'] + ': ' + msg['error'] + '\n');
        }

        this.handleApiError('Errors in the configuration file', errors);
      }
    } catch (e: any) {
      let error_msg = 'An error occured during fetching configuration.'; //this.showAlert(fullMessage);
      let error = this.handleApiError(error_msg, e);
      if (error.reason === 'not_initialized') {
        this.showAlert('The application is not initialized. You should fill in mandatory configuration parameters and run setup');
      }
    } finally {
      this.loading = false;
    }
  }

  private updateConfig(cfg: Configuration) {
    this.commit_link = cfg.commit_link;
    this.config_file = cfg.config_file;
    //this.form.controls['configfile'].setValue(cfg.configfile);
    for (let field of Object.keys(cfg.config)) {
      let control = this.form.controls[field];
      if (control) {
        control.setValue(cfg.config[field]);
      }
    }
  }
  async reload() {
    this.executeOp(async () => {
      let cfg = await this.configService.loadConfig();
      this.updateConfig(cfg);
    }, 'An error occured during fetching configuration');
  }

  async save() {
    let config = this.form.value;
    this.executeOp(async () => {
      await this.configService.updateConfig(config);
      this.editable = false;
      this.showSnackbar('Config updated');
    }, 'An error occured during updating configuration:', /*showAlert*/true);
  }
}
