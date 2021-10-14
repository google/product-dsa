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
import { Component, Inject, OnInit } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatTableDataSource } from '@angular/material/table';

export interface ObjectDetailsDialogData {
  row: any;
  dataSource: MatTableDataSource<any>;
}
@Component({
  templateUrl: './object-details-dialog.component.html',
  styleUrls: ['./object-details-dialog.component.css']
})
export class ObjectDetailsDialogComponent implements OnInit {
  fields: string[];
  currentIndex: number;

  constructor(@Inject(MAT_DIALOG_DATA) public data: ObjectDetailsDialogData) {
    this.fields = Object.keys(data.row);
    this.currentIndex = this.data.dataSource.data.indexOf(this.data.row);
  }

  ngOnInit(): void {
  }

  goPrev() {
    if (this.currentIndex > 0) {
      this.currentIndex--;
    } else {
      this.currentIndex = this.data.dataSource.data.length - 1;
    }
    this.data.row = this.data.dataSource.data[this.currentIndex];
  }
  goNext() {
    if (this.currentIndex < this.data.dataSource.data.length - 1) {
      this.currentIndex++;
    } else {
      this.currentIndex = 0;
    }
    this.data.row = this.data.dataSource.data[this.currentIndex];
  }
}
