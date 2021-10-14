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
import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot, UrlTree, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { ConfigComponent } from '../config.component';
import { ConfigService } from './config.service';
import { NotificatinService } from './notification.service';

@Injectable({
  providedIn: 'root'
})
export class DefaultRouteGuard implements CanActivate {
  constructor(private router: Router,
    private configService: ConfigService,
    private notificationService: NotificatinService) { }

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot): Observable<boolean | UrlTree> | Promise<boolean | UrlTree> | boolean | UrlTree {
    // TODO: why all this not working?!
    let is_proto = ConfigComponent.prototype.isPrototypeOf(<any>route.component);
    let is_ins = route.component instanceof ConfigComponent;
    let is_proto2 = Object.getPrototypeOf(route.component) === ConfigComponent

    if (!((<any>route.component).name === "ConfigComponent") && !this.configService.getConfig()) {
      return new Promise<boolean>((resolve) => {
        this.configService.loadConfig().then(config => {
          if (config.errors && config.errors.length) {
            this.notificationService.message = "Configuration contains error, please <a href='/config' routerLink='/config'>correct</a> before generating";
          }
          resolve(true);
        }).catch(error => {
          this.router.navigate(['/config']);
          resolve(false);
        })
      });
    }
    return true;
  }
}