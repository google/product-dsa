import { Pipe, PipeTransform } from "@angular/core";
import isPlainObject from 'lodash-es/isPlainObject'

@Pipe({name: 'app_json', pure: false})
export class JsonPipe implements PipeTransform {
  /**
   * @param value A value of any type to convert into a JSON-format string.
   */
  transform(value: any): string {
    if (isPlainObject(value)) {
      return JSON.stringify(value, null, 2);
    }
    return value;
  }
}