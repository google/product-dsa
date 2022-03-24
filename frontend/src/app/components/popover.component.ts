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
import {ChangeDetectionStrategy, Component, ElementRef, Input, OnInit, TemplateRef, ViewChild} from '@angular/core';
import {MatMenuTrigger, MenuPositionX, MenuPositionY} from '@angular/material/menu';

@Component({
  selector: 'app-popover',
  templateUrl: './popover.component.html',
  styleUrls: ['./popover.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CustomPopoverComponent implements OnInit {
  @Input()
  xPosition: MenuPositionX = 'after';

  @Input()
  yPosition: MenuPositionY = 'below';

  @Input()
  content!: TemplateRef<any>;

  @Input()
  mode: 'toggle' | 'hover' = 'toggle';

  // TODO: trigger is always undefined
  // @ViewChild(MatMenuTrigger, {read: MatMenuTrigger, static: false})
  // trigger!: MatMenuTrigger;

  constructor(private readonly elementRef: ElementRef) { }

  ngOnInit(): void {
    // if (this.mode === 'toggle') {
    //   this.trigger._handleClick = () => { };
    //   this.elementRef.nativeElement.addEventListener('click', () => this.trigger.toggleMenu());
    // } else {
    //   this.elementRef.nativeElement.addEventListener('mouseenter', () => this.trigger.openMenu());
    //   this.elementRef.nativeElement.addEventListener('mouseleave', () => this.trigger.closeMenu());
    // }
  }

  // open(): void {
  //   this.trigger.openMenu();
  // }

  // close(): void {
  //   this.trigger.closeMenu();
  // }
}


