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
import { Component, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatPaginator } from '@angular/material/paginator';
import { MatTableDataSource } from '@angular/material/table';
import { Subscription } from 'rxjs';
import { ComponentBase } from './components/component-base';
import { ObjectDetailsDialogComponent } from './components/object-details-dialog.component';
import { ConfigService, GetConfigResponse } from './shared/config.service';
import { NotificatinService } from './shared/notification.service';
import { ProductService } from './shared/product.service';

@Component({
  selector: 'app-products',
  templateUrl: './products.component.html',
  styleUrls: ['./products.component.scss']
})
export class ProductsComponent extends ComponentBase implements OnInit, OnDestroy {
  loading: boolean = false;
  formLabels: FormGroup;
  formProducts: FormGroup;
  dataSourceLabels: MatTableDataSource<any>;
  columnsLabels = ['label', 'count'];
  dataSourceProducts: MatTableDataSource<any>;
  columnsProducts = ['offer_id', 'title', 'brand', 'in_stock', 'custom_description'];
  @ViewChild('paginatorLabels') paginatorLabels: MatPaginator | undefined;
  @ViewChild('paginatorProducts') paginatorProducts: MatPaginator | undefined;
  private _subscription: Subscription | undefined;

  constructor(private fb: FormBuilder,
    private productService: ProductService,
    private configService: ConfigService,
    private dialog: MatDialog,
    notificationSvc: NotificatinService) {
    super(notificationSvc);

    this.formLabels = this.fb.group({
      mode: 'both'
    }, { updateOn: 'blur' });
    this.formProducts = this.fb.group({
      only_in_stock: false,
      only_long_description: false
    }, { updateOn: 'blur' });
    this.dataSourceLabels = new MatTableDataSource<any>();
    this.dataSourceProducts = new MatTableDataSource<any>();
  }

  ngOnInit(): void {
    this.showData();
    this._subscription = this.configService.currentTargetChanged.subscribe((value) => {
      this.showData();
    });
  }

  ngOnDestroy(): void {
    this._subscription?.unsubscribe();
  }

  ngAfterViewInit() {
    this.dataSourceLabels.paginator = this.paginatorLabels!;
    this.dataSourceProducts.paginator = this.paginatorProducts!;
  }

  showData() {
    let labels = this.productService.getLabels(this.configService.currentTarget!);
    this.showLabels(labels);
    let products = this.productService.getProducts(this.configService.currentTarget!);
    this.showProducts(products)
  }

  async loadLabels() {
    try {
      let filter = this.formLabels.get('mode')?.value;
      let categoryOnly = filter === 'category_only';
      let productOnly = filter === 'product_only';
      this.errorMessage = null;
      this.loading = true;
      this.dataSourceLabels.data = [];
      const data = await this.productService.loadLabels(this.configService.currentTarget!, { categoryOnly, productOnly });
      this.showLabels(data, true);
    } catch (e) {
      this.handleApiError(`Labels failed to load`, e);
    } finally {
      this.loading = false;
    }
  }

  showLabels(serverData: Record<string, any>[] | undefined, showNotifications: boolean = false) {
    this.dataSourceLabels.data = [];
    if (!serverData || !serverData.length) {
      if (showNotifications) {
        this.showSnackbar("No data found");
      }
      return;
    }
    this.dataSourceLabels.data = serverData;
  }

  async loadProducts() {
    try {
      this.errorMessage = null;
      let onlyLongDescription = !!this.formProducts.get('only_long_description')?.value;
      let onlyInStock = !!this.formProducts.get('only_in_stock')?.value;
      this.loading = true;
      this.dataSourceProducts.data = [];
      const data = await this.productService.loadProducts(this.configService.currentTarget!, { onlyInStock, onlyLongDescription });
      this.showProducts(data, true);
    } catch (e) {
      this.handleApiError(`Labels failed to load`, e);
    } finally {
      this.loading = false;
    }
  }

  showProducts(serverData: Record<string, any>[] | undefined, showNotifications: boolean = false) {
    this.dataSourceProducts.data = [];
    if (!serverData || !serverData.length) {
      if (showNotifications) {
        this.showSnackbar("No data found");
      }
      return;
    }
    this.dataSourceProducts.data = serverData;
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
