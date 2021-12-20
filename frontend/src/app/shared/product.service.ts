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
import { ApiService } from './api.service';

@Injectable({
  providedIn: 'root'
})
export class ProductService {
  labels: Record<string, Record<string, any>[]>;
  products: Record<string, Record<string, any>[]>;

  constructor(public apiService: ApiService) {
    this.labels = {};
    this.products = {};
  }

  getLabels(target: string): Record<string, any>[] | undefined {
    return this.labels[target];
  }

  async loadLabels(target: string, filter?: { categoryOnly?: boolean, productOnly?: boolean }): Promise<Record<string, any>[]> {
    let labels = await this.apiService.getLabels(target, filter?.categoryOnly, filter?.productOnly);
    this.labels[target] = labels;
    return labels;
  }

  getProducts(target: string): Record<string, any>[] | undefined {
    return this.products[target];
  }

  async loadProducts(target: string, filter?: { onlyInStock?: boolean, onlyLongDescription?: boolean}): Promise<Record<string, any>[]> {
    let products = await this.apiService.getProducts(target, filter?.onlyInStock, filter?.onlyLongDescription);
    this.products[target] = products;
    return products;
  }

  async updateProduct(target: string, product_id: string, values: Record<string, any>) {
    return this.apiService.updateProduct(target, product_id, values);
  }
}