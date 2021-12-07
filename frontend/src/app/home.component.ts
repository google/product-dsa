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
import { FormBuilder } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { CustomSnackBar } from './components/custom-snackbar.component';
import { GenerationComponentBase } from './components/generation-component-base';
import { GenerationService } from './shared/generation.service';
import { NotificatinService } from './shared/notification.service';

@Component({
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss']
})
export class HomeComponent extends GenerationComponentBase implements OnInit {
  loading: boolean = false;

  constructor(private fb: FormBuilder,
    private router: Router,
    private snackBar: MatSnackBar,
    generationService: GenerationService,
    notificationSvc: NotificatinService) {
    super(generationService, notificationSvc);
  }

  ngOnInit(): void {
  }

  openGuidedWizard() {
    this.router.navigate(['wizard']);
  }

  async updatePageFeed() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.generationService.generatePageFeed({ skipDownload: true });
      this.snackBar.openFromComponent(CustomSnackBar, {
        duration: 6000, data: {
          message: `Updated <a href="https://docs.google.com/spreadsheets/d/${res.spreadsheet_id}" target="_blank" class="primary-color">Google Spreadsheet</a> with page feed data`
        }
      });
    } catch (e) {
      this.handleApiError(`A failure occured`, e);
    } finally {
      this.loading = false;
    }
  }

  async updateAdCustomizers() {
    try {
      this.errorMessage = null;
      this.loading = true;
      let res = await this.generationService.generateAdcustomizers({ skipDownload: true });
      this.snackBar.openFromComponent(CustomSnackBar, {
        duration: 6000, data: {
          message: `Updated <a href="https://docs.google.com/spreadsheets/d/${res.spreadsheet_id}" target="_blank" class="primary-color">Google Spreadsheet</a> with ad customizers feed data`
        }
      });
    } catch (e) {
      this.handleApiError(`A failure occured`, e);
    } finally {
      this.loading = false;
    }
  }
}
