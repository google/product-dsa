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
import { Injectable } from '@angular/core';
import { MatDialog, MatDialogRef } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BehaviorSubject } from 'rxjs';
import { ConfirmationDialogComponent, ConfirmationDialogModes } from '../components/confirmation-dialog.component';

@Injectable({
  providedIn: 'root'
})
export class NotificatinService {
  changed: BehaviorSubject<string> = new BehaviorSubject<string>("");

  constructor(public dialog: MatDialog, public snackBar: MatSnackBar) { }

  private _message: string = "";
  set message(value: string) {
    this._message = value;
    this.changed.next(value);
  }
  get message() {
    return this._message;
  }

  showSnackbarWithError(message: string, e: any) {
    let snackBarRef = this.snackBar.open(message, 'Details', {
      duration: 6000,
    });
    snackBarRef.onAction().subscribe(() => {
      let details = '';
      typeof e === 'string' ? details = e : details = JSON.stringify(e);
      snackBarRef.dismiss();
      snackBarRef = this.snackBar.open(details, 'Dismiss', {
        duration: 15000,
      });
      snackBarRef.onAction().subscribe(() => {
        snackBarRef.dismiss();
      });
    });
  }

  /**
   * Show a snackbar (popup at the bottom) with an information message
   * @param message A user message
   */
  showSnackbar(message: string) {
    const snackBarRef = this.snackBar.open(message, 'Dismiss', {
      duration: 4000,
    });
    snackBarRef.onAction().subscribe(() => {
      snackBarRef.dismiss();
    });
  }

  /**
   * Show a confirmation dialog (with Yes/No)
   * @param message a user message
   * @returns Dialog
   */
  confirm(message: string) {
    const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
      data: {
        message,
        mode: ConfirmationDialogModes.YesNo
      }
    });
    return dialogRef;
  }

  showAlert(message: string, header?: string): MatDialogRef<ConfirmationDialogComponent> {
    return this.dialog.open(ConfirmationDialogComponent, {
      data: {
        message: message,
        header: header,
        mode: ConfirmationDialogModes.Ok
      }
    });
  }

  showAlertHtml(html: string, header?: string): MatDialogRef<ConfirmationDialogComponent> {
    return this.dialog.open(ConfirmationDialogComponent, {
      data: {
        html: html,
        header: header,
        mode: ConfirmationDialogModes.Ok
      }
    });
  }
}