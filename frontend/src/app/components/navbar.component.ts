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
import { Component } from '@angular/core';
import { ConfigService } from '../shared/config.service';

interface Target {
  name: string;
}
@Component({
  selector: 'app-navbar',
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.scss']
})
export class NavbarComponent {
  targets: Target[] = [];
  selectedTarget: string = '';
  constructor(private configService: ConfigService) {
    configService.loaded.subscribe(cfg => {
      if (cfg) {
        this.targets = cfg.targets;
        this.selectedTarget = '';
        if (this.targets && this.targets.length > 0) {
          this.selectedTarget = this.targets[0].name;
        }
      } else {
        this.selectedTarget = '';
      }
      this.configService.currentTarget = this.selectedTarget;
    });
  }
  onTargetChanged(val: string) {
    this.configService.currentTarget = val;
  }
}
