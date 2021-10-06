import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot, UrlTree, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { ConfigComponent } from '../config.component';
import { ConfigService } from './config.service';


@Injectable({
  providedIn: 'root'
})
export class DefaultRouteGuard implements CanActivate {
  constructor(private router: Router, private configService: ConfigService) { }

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot): Observable<boolean | UrlTree> | Promise<boolean | UrlTree> | boolean | UrlTree {
    // TODO: why all this not working?!
    let is_proto = ConfigComponent.prototype.isPrototypeOf(<any>route.component);
    let is_ins = route.component instanceof ConfigComponent;
    let is_proto2 = Object.getPrototypeOf(route.component) === ConfigComponent

    if (!((<any>route.component).name === "ConfigComponent") && !this.configService.getConfig()) {
      return new Promise<boolean>((resolve) => {
        this.configService.loadConfig().then(config => {
          resolve(true);
        }).catch(error => {
          this.router.navigate(['/config']);
          resolve(false);
        })
      });
    }

    return true;
  }

}