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
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {MatSnackBar} from '@angular/material/snack-bar';
import {ConfirmationDialogComponent, ConfirmationDialogModes} from './confirmation-dialog.component';

export abstract class ComponentBase {
  errorMessage: string | null = null;
  loading = false;

  constructor(
    public dialog: MatDialog,
    public snackBar: MatSnackBar) {

  }

  closeErrorMessage() {
    this.errorMessage = '';
  }

  handleApiError(message: string, e: any, showAlert: boolean = false) {
    let details = e.message;
    let error = e;
    if (e.error) {
      error = e.error;
      details = e.error.error;
    }
    let fullMessage = message + (details ? ": " + details : "")
    this.errorMessage = fullMessage.replace(/(?:\r\n|\r|\n)/g, '<br>');
    if (showAlert) {
      if (typeof error !== 'string') {
        message = message + " " + JSON.stringify(error);
      } else {
        message = message + " " + error;
      }
      this.showAlert(message);
    } else {
      this.showSnackbarWithError(message, error);
    }
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

  showAlert(message: string): MatDialogRef<ConfirmationDialogComponent> {
    return this.dialog.open(ConfirmationDialogComponent, {
      data: {
        message: message,
        mode: ConfirmationDialogModes.Ok
      }
    });
  }

  onTableRowClick($event: MouseEvent): boolean {
    // ignore click on links
    if ((<any>$event.target).tagName === 'A') {return false;}
    // ignore click on button
    let el = <any>$event.target;
    do {
      if ((el).tagName === 'BUTTON') {return false;}
      el = el.parentElement;
    } while (el && el !== $event.currentTarget);

    return true;
  }

  async executeOp<T>(action: () => T, errorMsg: string, showAlert: boolean = false): Promise<T | void> {
    try {
      this.loading = true;
      this.errorMessage = null;
      return await action();
    } catch (e) {
      this.handleApiError(errorMsg, e, showAlert);
    } finally {
      this.loading = false;
    }
  }
}
