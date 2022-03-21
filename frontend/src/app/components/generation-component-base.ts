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
import {ComponentBase} from './component-base';
import { GenerateCampaignOptions, GenerationService } from '../shared/generation.service';
import { NotificatinService } from '../shared/notification.service';

export abstract class GenerationComponentBase extends ComponentBase {
  constructor(protected generationService: GenerationService,
    notificationSvc: NotificatinService) {
    super(notificationSvc);
  }

  public async generateAdCampaign(images_dry_run?: boolean) {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.generationService.generateAdCampaign({ images_dry_run });
      if (res && res.filename) {
        // a large file saved on GCS but the server couldn't generate a downloadable link
        // res.filename: gcs://project_bucket/file_name
        let gcs_browser_link = '';
        let rePath = new RegExp("gs://(?<bucket>[^/]+)/(?<path>.+)");
        let match = rePath.exec(res.filename);
        if (match && match.groups) {
          let bucket = match.groups['bucket'];
          let path = match.groups['path'];
          // extract project id from GCS bucket name as the bucket is projectid + "-pdsa"
          let project = bucket.substring(0, bucket.length - "-pdsa".length);
          gcs_browser_link = `https://console.cloud.google.com/storage/browser/_details/${bucket}/${path}?project=${project}`;
        }
        this.notificationSvc.showAlertHtml(`Campaign data generated and uploaded to Google Cloud Storage - ${res.filename}. <a href='${gcs_browser_link}' target='_blank' class='accent-color'>Open</a>.`, 'Success');
      }
    } catch (e) {
      this.handleApiError(`A failure occured`, e);
    } finally {
      this.loading = false;
    }
  }
}
