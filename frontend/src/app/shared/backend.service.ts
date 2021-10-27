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
import { HttpClient, HttpErrorResponse, HttpHeaders, HttpResponse } from '@angular/common/http';
import { saveAs } from 'file-saver';
import { lastValueFrom, Observable, Subject, throwError } from 'rxjs';
import { catchError, tap, map } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class BackendService {
  constructor(private http: HttpClient) { }
  baseUrl = '/api';

  private getBaseHeaders(opt?: { emptyResponse?: boolean }): HttpHeaders {
    let headers = new HttpHeaders({
      'Accept': opt?.emptyResponse ? '*' : 'application/json',
      'Content-Type': 'application/json',
    });
    return headers; //this.addAuthorization(headers);
  }

  private getUrl(url: string) {
    if (!url) { throw new Error(`[BackendService] url must be specified`); }
    if (!url.startsWith('/')) { url = '/' + url; }
    return this.baseUrl + url;
  }


  async getApi<T>(url: string, params?: Record<string, any>): Promise<T> {

    return lastValueFrom(this.http.get<T>(
      this.getUrl(url),
      {
        headers: this.getBaseHeaders(),
        params
      }));
  }

  postApi(url: string, payload?: any, opt?: { emptyResponse?: boolean, params?: Record<string, any> }): Promise<any> {
    let options: any = { headers: this.getBaseHeaders(opt) };
    if (opt?.emptyResponse)
      options['responseType'] = 'text';
    options.params = options?.params;
    return lastValueFrom(this.http.post(
      this.getUrl(url),
      payload,
      options)
    );
  }

  async getFile(url: string, params?: Record<string, any>): Promise<void> {
    const headers = this.getBaseHeaders()
      .set('Content-Type', 'application/x-www-form-urlencoded');
    try {
      let res = await lastValueFrom(this.http.get<Blob>(this.getUrl(url), {
        responseType: 'blob' as 'json',
        observe: 'response',
        headers,
        params
      }));
      const fileName = this.getFileNameFromHttpResponse(res);
      saveAs(res.body!, fileName);
    } catch (e: any) {
      if (e.error && Object.getPrototypeOf(e.error).toString() === '[object Blob]') {
        const errorJson = await (<Blob>e.error).text();
        try {
          const error = JSON.parse(errorJson);
          e.error = error;
        } catch { }
      }
      throw e;
    }
  }

  private getFileNameFromHttpResponse(httpResponse: HttpResponse<Blob>) {
    const contentDispositionHeader = httpResponse.headers.get('Content-Disposition');
    if (!contentDispositionHeader) return '';
    const result = contentDispositionHeader.split(';')[1].trim().split('=')[1];
    return result.replace(/"/g, '');
  }
}
