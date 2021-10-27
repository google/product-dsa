import { StepperSelectionEvent } from '@angular/cdk/stepper';
import { Component, OnInit } from '@angular/core';
import { FormArray, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ErrorStateMatcher } from '@angular/material/core';
import { ComponentBase } from './components/component-base';
import { ConfigError, ConfigService, Configuration } from './shared/config.service';
import { CustomErrorStateMatcher } from './shared/ErrorStateMatcher';
import { NotificatinService } from './shared/notification.service';

@Component({
  selector: 'app-setup',
  templateUrl: './setup.component.html',
  styleUrls: ['./setup.component.scss']
})
export class SetupComponent extends ComponentBase implements OnInit {
  loading: boolean = false;
  form: FormGroup;
  matcher: ErrorStateMatcher = new CustomErrorStateMatcher();
  service_account = "PROJECT_ID@appspot.gserviceaccount.com";

  constructor(private fb: FormBuilder,
    private configService: ConfigService,
    notificationSvc: NotificatinService) {
    super(notificationSvc);
    this.form = fb.group({ // NOTE: add type <Configuration> to validate fields
      merchant_id: ['', [Validators.required]],
      dataset_id: '',
      dataset_location: '',
      dt_schedule: '',
      //pubsub_topic_dt_finish: '',
      targets: fb.array([this.createTargetFormGroup()])
    });
  }

  ngOnInit(): void {
    // extract project_id from current url
    if (location.hostname.endsWith('appspot.com')) {
      this.service_account = location.hostname.split('.')[0];
    }
  }

  get targets(): FormArray {
    return <FormArray>this.form.get('targets');
  }

  onStep(event: StepperSelectionEvent) {
    console.log(event.selectedStep.interacted);
  }

  private applyErrors(config: Configuration, errors?: ConfigError[]) {
    if (errors && errors.length) {
      for (let error_obj of errors) {
        if (error_obj.field.startsWith('targets.') && config.targets?.length) {
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

  createTargetFormGroup() {
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
    return this.fb.group(group_spec);
  }

  addTarget() {
    this.targets.push(this.createTargetFormGroup());
    //this.dataSourceLabelDescs.push(new MatTableDataSource<any>([]));
  }

  deleteTarget(i: number) {
    this.targets.removeAt(i);
    //this.dataSourceLabelDescs.splice(i, 1);
  }

  async save() {
    let config = this.form.value;
    // for (let i = 0; i < config.targets.length; i++) {
    //   let map: Record<string, string> = {};
    //   this.dataSourceLabelDescs[i].data.forEach(fg => {
    //     map[<string>fg.get("label").value] = fg.get("description").value;
    //   });
    //   config.targets[i].category_ad_descriptions = map;
    // }
    await this.executeOp(async () => {
      let res = await this.configService.updateConfig(config);
      if (!res.errors || !res.errors.length) {
        this.showSnackbar('Configuration saved');
      } else {
        this.applyErrors(config, res.errors);
      }
    }, 'An error occured during updating configuration', /*showAlert*/true);
  }

  async runSetup() {
    let config = this.form.value;
    if (this.form.invalid) {
      this.showAlert('Please fix all validation error');
      return;
    }
    this.executeOp(async () => {
      let response = await this.configService.apiService.runSetup({}, config);
      let log = response.log;
      console.log(log);
      // if (log && log.length) {
      //   this.showLog(log);
      // }
      this.showAlert("Application setup has completed", "Congratulation");
      // TODO: should we analyze labels (response.labels) here?
    }, 'Setup failed', true);
  }
}
