import { FormControl, FormGroupDirective, NgForm } from "@angular/forms";
import { ErrorStateMatcher } from "@angular/material/core";

/**
 * A custom error state matcher for reactive forms
 * (can be used via [matcher]="CustomErrorStateMatcher" in form's layout).
 * In contract to the default error state matcher this one report error state only based on control's invalid property.
 */
export class CustomErrorStateMatcher implements ErrorStateMatcher {
  isErrorState(control: FormControl | null, form: FormGroupDirective | NgForm | null): boolean {
    return control?.invalid || false;
  }
}