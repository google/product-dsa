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
import { Component, HostListener, Inject, OnInit } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';

export interface EditValueDialogData {
  label: string;
  value: any;
  maxLength?: number;
  minLength?: number;
}

@Component({
  template: `
<h1 mat-dialog-title>Edit</h1>
<div mat-dialog-content>
  <mat-form-field appearance="outline" class="full-width" color="accent">
    <mat-label>{{ data.label }}</mat-label>
    <input matInput [(ngModel)]="value" maxlength="{{data.maxLength}}" minLength="{{data.minLength}}">
    <mat-hint align="end">{{value?.length || 0}} / {{data.maxLength}}</mat-hint>
  </mat-form-field>
</div>
<div mat-dialog-actions class="mt-15" style="text-align: center;">
  <div class="full-width">
    <button mat-raised-button color="primary" type="submit" [mat-dialog-close]="value" cdkFocusInitial>Ok</button>
    <button mat-raised-button mat-dialog-close>Cancel</button>
  </div>
</div>
  `
})
export class EditValueDialogComponent {
  value: string;
  constructor(@Inject(MAT_DIALOG_DATA) public data: EditValueDialogData,
    private dialogRef: MatDialogRef<EditValueDialogComponent>) {
    this.value = data.value;
  }

  @HostListener('window:keyup.Enter', ['$event'])
  onDialogClick(event: KeyboardEvent): void {
    this.dialogRef.close(this.value);
  }
}
