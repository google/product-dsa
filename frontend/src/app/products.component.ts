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
import { ApiService } from './shared/api.service';

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
  @ViewChild('paginatorLabels') paginatorLabels: MatPaginator | undefined;

  constructor(private fb: FormBuilder,
    private apiService: ApiService,
    dialog: MatDialog,
    snackBar: MatSnackBar) {
    super(dialog, snackBar);

    this.formLabels = this.fb.group({
    }, { updateOn: 'blur' });
    this.formProducts = this.fb.group({
    }, { updateOn: 'blur' });
    this.dataSourceLabels = new MatTableDataSource<any>();
  }

  ngOnInit(): void {
  }

  ngAfterViewInit() {
    this.dataSourceLabels.paginator = this.paginatorLabels!;
  }

  async loadLabels() {
    try {
      this.errorMessage = null;
      this.loading = true;
      const data = await this.apiService.getLabels();
      this.showLabels(data);
    } catch (e) {
      this.handleApiError(`Labels failed to load`, e);
    } finally {
      this.loading = false;
    }
  }

  showLabels(serverData: Record<string, any>[]) {
    // let serverData: Record<string, any>[] = [
    //   { label: "product-1", count: 1 },
    //   { label: "product-2", count: 1 },
    //   { label: "product-3", count: 1 },
    // ];
    if (!serverData || !serverData.length) { return; }
    this.dataSourceLabels.data = serverData;
    this.columnsLabels = Object.keys(serverData[0]);
  }
}
