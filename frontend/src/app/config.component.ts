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
import { FormArray, FormBuilder, FormControl, FormGroup, FormGroupDirective, NgForm, Validators } from '@angular/forms';
import { ErrorStateMatcher } from '@angular/material/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ComponentBase } from './components/component-base';
import { ApiService } from './shared/api.service';
import { ConfigError, ConfigService, Configuration, ConfigurationTarget, GetConfigResponse, TargetNames } from './shared/config.service';

class CustomErrorStateMatcher implements ErrorStateMatcher {
  isErrorState(control: FormControl | null, form: FormGroupDirective | NgForm | null): boolean {
    return control?.invalid || false;
  }

}
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
  config: Configuration | undefined;
  matcher: ErrorStateMatcher = new CustomErrorStateMatcher();

  constructor(private fb: FormBuilder,
    private configService: ConfigService,
    dialog: MatDialog,
    snackBar: MatSnackBar) {
    super(dialog, snackBar);
    this.form = fb.group({ // NOTE: add type <Configuration> to validate fields
      project_id: '',
      merchant_id: '',
      dataset_id: '',
      dataset_location: '',
      //page_feed_name: '',
      //page_feed_spreadsheetid: '',
      //adcustomizer_feed_name: '',
      //adcustomizer_spreadsheetid: '',
      //ad_description_template: '',
      //dsa_lang: '',
      //dsa_website: '',
      dt_schedule: '',
      pubsub_topic_dt_finish: '',
      targets: fb.array([])
    });
  }

  get targets(): FormArray {
    return <FormArray>this.form.get('targets');
  }

  async ngOnInit() {
    let cfg = this.configService.getConfig();
    if (cfg) {
      this.updateConfig(cfg);
    }
    else {
      this.reload();
    }
  }

  private updateConfig(cfg: GetConfigResponse) {
    this.commit_link = cfg.commit_link;
    this.config_file = cfg.config_file;
    this.config = cfg.config;
    this.config.targets = this.config.targets || [];

    for (let field of Object.keys(cfg.config)) {
      let control = this.form.controls[field];
      if (control && !(control instanceof FormArray)) {
        control.setValue((<any>cfg.config)[field]);
      }

    }
    this.targets.clear();
    for (const target of this.config.targets) {
      let group_spec: any = {};
      for (const field of Object.keys(target)) {
        group_spec[field] = (<any>target)[field];
      }
      this.targets.push(this.fb.group(group_spec));
    }
    // show validation error (if any)
    setTimeout(() => {
      this.applyErrors(cfg.config, cfg.errors);
    }, 0);
  }

  private applyErrors(config: Configuration, errors?: ConfigError[]) {
    if (errors && errors.length) {
      for (let error_obj of errors) {
        if (error_obj.field.startsWith('targets.')) {
          let parts = error_obj.field.split('.');
          if (parts.length === 3) {
            let name = parts[1];
            // find a target form group for the name
            let idx = config.targets.findIndex(t => t.name === name);
            let target_control = this.targets.at(idx);
            let control = target_control.get(parts[2]);
            if (control) {
              // TODO: for some reason it's not working (no error displayed)
              control.setErrors({ invalid: error_obj.error });
            }
          }
        } else {
          let control = this.form.get(error_obj.field);
          if (control) {
            control.setErrors({ invalid: error_obj.error });
          }
        }
      }
      let error: any = { error: '' };
      for (var msg of errors) {
        error.error += (msg['field'] + ': ' + msg['error'] + '\n');
      }
      this.handleApiError('Errors in the configuration file', error);
    }

  }

  addTarget() {
    let group_spec = {  // NOTE: specify type ConfigurationTarget to validate fields
      name: ['', [Validators.required]],  // TODO: validator for name format (only valid symbols)
      merchant_id: '',
      //ads_customer_id: '',
      product_campaign_name: '',
      category_campaign_name: '',
      dsa_website: '', //
      dsa_lang: '',   //
      page_feed_name: '', //
      page_feed_spreadsheetid: '', //
      adcustomizer_feed_name: '', //
      adcustomizer_spreadsheetid: '', //
      ad_description_template: '', //
      category_ad_descriptions: null
    };
    this.targets.push(this.fb.group(group_spec));
  }

  deleteTarget(i: number) {
    this.targets.removeAt(i);
  }

  async reload() {
    try {
      this.loading = true;
      let cfg = await this.configService.loadConfig();
      this.updateConfig(cfg);
    } catch (e: any) {
      let error_msg = 'An error occured during fetching configuration.'; //this.showAlert(fullMessage);
      let error = this.handleApiError(error_msg, e);
      if (error.reason === 'not_initialized') {
        this.showAlert('The application is not initialized. You should fill in mandatory configuration parameters and run setup');
      }
    } finally {
      this.loading = false;
    }
    // this.executeOp(async () => {
    //   let cfg = await this.configService.loadConfig();
    //   this.updateConfig(cfg);
    // }, 'An error occured during fetching configuration');
  }

  async save() {
    let config = this.form.value;
    this.executeOp(async () => {
      let res = await this.configService.updateConfig(config);
      if (!res.errors || !res.errors.length) {
        this.showSnackbar('Config updated');
      } else {
        this.applyErrors(this.config!, res.errors);
      }
      this.editable = false;
    }, 'An error occured during updating configuration:', /*showAlert*/true);
  }
}
