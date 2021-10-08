import { Injectable } from '@angular/core';
import { ApiService } from './api.service';

@Injectable({
  providedIn: 'root'
})
export class ProductService {
  labels: Record<string, any>[] | undefined;
  products: Record<string, any>[] | undefined;

  constructor(public apiService: ApiService) { }

  getLabels(): Record<string, any>[] | undefined {
    return this.labels;
  }

  async loadLabels(target: string): Promise<Record<string, any>[]> {
    this.labels = await this.apiService.getLabels(target);
    return this.labels;
  }

  getProducts(): Record<string, any>[] | undefined {
    return this.products;
  }

  async loadProducts(target: string): Promise<Record<string, any>[]> {
    this.products = await this.apiService.getProducts(target);
    return this.products;
  }
}