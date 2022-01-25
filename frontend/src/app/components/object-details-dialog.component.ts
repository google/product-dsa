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
import { Component, Inject, OnInit } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { MatDialog, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatTableDataSource } from '@angular/material/table';
import { ConfigService } from '../shared/config.service';
import { NotificatinService } from '../shared/notification.service';
import { ProductService } from '../shared/product.service';
import { ComponentBase } from './component-base';
import { EditValueDialogComponent } from './edit-value-dialog.component';

const AD_DESCRIPTION_MAX_LENGTH = 90;
const AD_DESCRIPTION_MIN_LENGTH = 35;

export interface ObjectDetailsDialogData {
  row: any;
  dataSource: MatTableDataSource<any>;
}
@Component({
  templateUrl: './object-details-dialog.component.html',
  styleUrls: ['./object-details-dialog.component.css']
})
export class ObjectDetailsDialogComponent extends ComponentBase implements OnInit {
  fields: string[];
  currentIndex: number;

  constructor(@Inject(MAT_DIALOG_DATA) public data: ObjectDetailsDialogData,
    notificationSvc: NotificatinService,
    private dialog: MatDialog,
    private productService: ProductService,
    private configService: ConfigService) {
    super(notificationSvc);
    this.fields = Object.keys(data.row);
    let top_fields = ['custom_description', 'title', 'description', 'price', 'sale_price', 'brand'];
    this.fields = this.fields.filter((value, index, array) => {
      return !top_fields.includes(value);
    });
    this.fields = top_fields.concat(this.fields);
    this.currentIndex = this.data.dataSource.data.indexOf(this.data.row);
  }

  ngOnInit(): void {
  }

  shouldShowTextLength(field: string): boolean {
    return field === 'custom_description' || field === 'title' || field === 'description';
  }

  edit_description(object: any) {
    const dialogRef = this.dialog.open(EditValueDialogComponent, {
      width: '600px',
      data: {
        label: 'description',
        value: object['custom_description'],
        maxLength: AD_DESCRIPTION_MAX_LENGTH,
        minLength: AD_DESCRIPTION_MIN_LENGTH
      }
    });
    dialogRef.afterClosed().subscribe(result => {
      let oldVal = object['custom_description'] || '';
      let newVal = result?.trim() || '';
      if (newVal && newVal !== oldVal) {
        object['custom_description'] = newVal;
        const product_id = object['offer_id'];
        const product_data = { custom_description: newVal };
        this.loading = true;
        this.productService.updateProduct(this.configService.currentTarget!, product_id, product_data).then(() => {
          this.loading = false;
          this.showSnackbar('Product description has been updated');
        }, (e: any) => {
          this.handleApiError('Save failed', e);
        });
      }
    });
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
