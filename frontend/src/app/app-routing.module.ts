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
import { RouterModule, Routes } from '@angular/router';
import { HomeComponent } from './home.component';
import { ProductsComponent } from './products.component';
import { ConfigComponent } from './config.component';
import { WizardComponent } from './wizard.component';
import { DefaultRouteGuard } from './shared/default-route.guard';

const routes: Routes = [
  { path: '', component: HomeComponent, canActivate: [DefaultRouteGuard] },
  { path: 'products', component: ProductsComponent, canActivate: [DefaultRouteGuard] },
  { path: 'wizard', component: WizardComponent, canActivate: [DefaultRouteGuard] },
  { path: 'config', component: ConfigComponent, canActivate: [DefaultRouteGuard] }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
