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

import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';

import { AppRoutingModule } from './app-routing.module';
import { AppMaterialModule } from './app-material.module';
import { AppComponent } from './app.component';
import { HomeComponent } from './home.component';
import { ProgressSpinnerComponent } from './components/progress-spinner.component';
import { NavbarComponent } from './components/navbar.component';
import { OverlayService } from './components/overlay.service';
import { ProductsComponent } from './products.component';
import { WizardComponent } from './wizard.component';
import { ObjectDetailsDialogComponent } from './components/object-details-dialog.component';
import { CustomSnackBar } from './components/custom-snackbar.component';
import { ConfigComponent } from './config.component';
import { CommonModule } from '@angular/common';
import { ConfirmationDialogComponent } from './components/confirmation-dialog.component';
import { DefaultRouteGuard } from './shared/default-route.guard';
import { NotificationBarComponent } from './components/notification-bar.component';
import { JsonPipe } from './components/json.pipe';
import { SetupComponent } from './setup.component';

@NgModule({
  declarations: [
    AppComponent,
    ProgressSpinnerComponent,
    NavbarComponent,
    ConfirmationDialogComponent,
    ObjectDetailsDialogComponent,
    CustomSnackBar,
    HomeComponent,
    ProductsComponent,
    WizardComponent,
    ConfigComponent,
    NotificationBarComponent,
    JsonPipe,
    SetupComponent
  ],
  imports: [
    BrowserModule,
    BrowserAnimationsModule,
    AppMaterialModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    AppRoutingModule,
    CommonModule
  ],
  providers: [OverlayService, DefaultRouteGuard],
  bootstrap: [AppComponent]
})
export class AppModule { }
