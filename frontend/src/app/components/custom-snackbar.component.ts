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
import { Component, OnInit, Inject, SecurityContext } from "@angular/core";
import {
  MatSnackBarRef,
  MAT_SNACK_BAR_DATA
} from "@angular/material/snack-bar";
import { DomSanitizer, SafeHtml } from "@angular/platform-browser";

@Component({
  selector: "app-basic-snackbar",
  templateUrl: 'custom-snackbar.component.html',
})
export class CustomSnackBar implements OnInit {
  html: SafeHtml;

  constructor(
    public sbRef: MatSnackBarRef<CustomSnackBar>,
    @Inject(MAT_SNACK_BAR_DATA) public data: any,
    private sanitized: DomSanitizer
  ) {
    if (data.html) {
      this.html = this.sanitized.bypassSecurityTrustHtml(data.html);
    } else if (data.message) {
      this.html = this.sanitized.sanitize(SecurityContext.HTML, data.message) || '';
    } else {
      throw new Error('Either html or message properties should be specified');
    }
  }
  ngOnInit() { }
}