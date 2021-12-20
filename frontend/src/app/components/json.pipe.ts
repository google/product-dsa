import { Pipe, PipeTransform } from "@angular/core";
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