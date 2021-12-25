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
import { MatDialogRef } from '@angular/material/dialog';
import { NotificatinService } from '../shared/notification.service';
import { ConfirmationDialogComponent } from './confirmation-dialog.component';

export abstract class ComponentBase {
  errorMessage: string | null = null;
  loading = false;

  constructor(protected notificationSvc: NotificatinService) {
  }

  closeErrorMessage() {
    this.errorMessage = '';
  }

  handleApiError(message: string, e: any, showAlert: boolean = false) {
    let error = e;
    let details = e.message;
    let reason = '';
    if (e.error) {
      // first 'error' is a deserialized http response's body
      error = e.error;
      if (typeof error === 'string') {
        details = error;
      }
      else if (error.error) {
        // we've got a response with a JSON object containing error field: {"error": ..}
        error = error.error;
        // but inside error's value there could be another level of details - object {description: "", reason: ""}
        details = error.description;
        reason = error.reason;
      }
      if (!details) {
        details = JSON.stringify(error);
      }
    }
    let fullMessage = message + (details ? ": " + details : "")
    fullMessage = fullMessage.replace(/>/g, "&gt;")
      .replace(/</g, "&lt;")
      .replace(/\\n/g, '<br>')
      .replace(/\r\n|\r|\n/g, '<br>');
    this.errorMessage = fullMessage;
    if (showAlert) {
      this.showAlert(fullMessage);
    } else {
      this.showSnackbarWithError(message, error);
    }
    return error;
  }

  showSnackbarWithError(message: string, e: any) {
    this.notificationSvc.showSnackbarWithError(message, e);
  }

  /**
   * Show a snackbar (popup at the bottom) with an information message
   * @param message A user message
   */
  showSnackbar(message: string) {
    this.notificationSvc.showSnackbar(message);
  }

  /**
   * Show a confirmation dialog (with Yes/No)
   * @param message a user message
   * @returns Dialog
   */
  confirm(message: string) {
    return this.notificationSvc.confirm(message);
  }

  showAlert(message: string, header?: string): MatDialogRef<ConfirmationDialogComponent> {
    return this.notificationSvc.showAlert(message, header);
  }

  onTableRowClick($event: MouseEvent): boolean {
    // ignore click on links
    if ((<any>$event.target).tagName === 'A') { return false; }
    // ignore click on button
    let el = <any>$event.target;
    do {
      if ((el).tagName === 'BUTTON') { return false; }
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
