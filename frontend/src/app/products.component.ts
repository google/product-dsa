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
import { Component, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatPaginator } from '@angular/material/paginator';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableDataSource } from '@angular/material/table';
import { ComponentBase } from './components/component-base';
import { ObjectDetailsDialogComponent } from './components/object-details-dialog.component';
import { ConfigService, GetConfigResponse } from './shared/config.service';
import { ProductService } from './shared/product.service';

@Component({
  selector: 'app-products',
  templateUrl: './products.component.html',
  styleUrls: ['./products.component.scss']
})
export class ProductsComponent extends ComponentBase implements OnInit {
  loading: boolean = false;
  formLabels: FormGroup;
  formProducts: FormGroup;
  dataSourceLabels: MatTableDataSource<any>;
  columnsLabels: string[] | undefined;
  dataSourceProducts: MatTableDataSource<any>;
  columnsProducts = ['offer_id', 'title', 'brand', 'in_stock', 'pdsa_custom_labels'];
  @ViewChild('paginatorLabels') paginatorLabels: MatPaginator | undefined;
  @ViewChild('paginatorProducts') paginatorProducts: MatPaginator | undefined;
  config: any;
  //selectedTarget: string | undefined;

  constructor(private fb: FormBuilder,
    private productService: ProductService,
    private configService: ConfigService,
    dialog: MatDialog,
    snackBar: MatSnackBar) {
    super(dialog, snackBar);

    this.formLabels = this.fb.group({
    }, { updateOn: 'blur' });
    this.formProducts = this.fb.group({
    }, { updateOn: 'blur' });
    this.dataSourceLabels = new MatTableDataSource<any>();
    this.dataSourceProducts = new MatTableDataSource<any>();
    this.config = this.configService.getConfig()!.config;
    // if (this.config.targets) {
    //   if (this.config.targets.length >= 1) {
    //     this.selectedTarget = this.config.targets[0].name;
    //   }
    // }
    // if (!this.selectedTarget) {
    //   // show some warning
    // }
  }

  ngOnInit(): void {
    let labels = this.productService.getLabels();
    if (labels) {
      this.showLabels(labels);
    }
    let products = this.productService.getProducts();
    if (products) {
      this.showProducts(products)
    }
  }

  ngAfterViewInit() {
    this.dataSourceLabels.paginator = this.paginatorLabels!;
    this.dataSourceProducts.paginator = this.paginatorProducts!;
  }

  async loadLabels() {
    try {
      this.errorMessage = null;
      this.loading = true;
      this.dataSourceLabels.data = [];
      const data = await this.productService.loadLabels(this.configService.currentTarget!);
      this.showLabels(data);
    } catch (e) {
      this.handleApiError(`Labels failed to load`, e);
    } finally {
      this.loading = false;
    }
  }

  showLabels(serverData: Record<string, any>[]) {
    if (!serverData || !serverData.length) {
      this.showSnackbar("No data found");
      return;
    }
    this.dataSourceLabels.data = serverData;
    this.columnsLabels = Object.keys(serverData[0]);
  }

  async loadProducts() {
    try {
      this.errorMessage = null;
      this.loading = true;
      this.dataSourceProducts.data = [];
      const data = await this.productService.loadProducts(this.configService.currentTarget!);
      this.showProducts(data);
    } catch (e) {
      this.handleApiError(`Labels failed to load`, e);
    } finally {
      this.loading = false;
    }
  }

  showProducts(serverData: Record<string, any>[]) {
    if (!serverData || !serverData.length) {
      this.showSnackbar("No data found");
      return;
    }
    this.dataSourceProducts.data = serverData;
    //this.columnsProducts = Object.keys(serverData[0]);
  }

  mouseOverIndex = -1;
  onProductDetails($event: MouseEvent, row: any, ds: MatTableDataSource<any>) {
    if (!this.onTableRowClick($event)) { return; }
    const dialogRef = this.dialog.open(ObjectDetailsDialogComponent, {
      width: '600px',
      data: {
        row,
        dataSource: ds
      }
    });
  }
}
