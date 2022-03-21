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
import {Pipe, PipeTransform} from "@angular/core";
import isPlainObject from 'lodash-es/isPlainObject'
import isArray from 'lodash-es/isArray'

@Pipe({name: 'app_json', pure: false})
export class JsonPipe implements PipeTransform {
  _get_value(value: any): string {
    if (isPlainObject(value)) {
      return JSON.stringify(value, null, 2);
    }
    return value;
  }
  /**
   * @param value A value of any type to convert into a JSON-format string.
   */
  transform(value: any): string {
    if (isArray(value)) {
      let str = '';
      for (let i of value) {
        str += this._get_value(i) + '\n';
        //str += i + '\n';
      }
      value = str;
    } else {
      value = this._get_value(value);
    }
    return value;
  }
}
