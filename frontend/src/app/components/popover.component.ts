import { ChangeDetectionStrategy, Component, ElementRef, Input, OnInit, TemplateRef, ViewChild } from '@angular/core';
import { MatMenuTrigger, MenuPositionX, MenuPositionY } from '@angular/material/menu';

@Component({
  selector: 'app-popover',
  templateUrl: './popover.component.html',
  styleUrls: ['./popover.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CustomPopoverComponent implements OnInit {
  @Input()
  xPosition: MenuPositionX = 'after';

  @Input()
  yPosition: MenuPositionY = 'below';

  @Input()
  content!: TemplateRef<any>;

  @Input()
  mode: 'toggle' | 'hover' = 'toggle';

  @ViewChild(MatMenuTrigger) trigger!: MatMenuTrigger;

  constructor(private readonly elementRef: ElementRef) { }

  ngOnInit(): void {
    if (this.mode === 'toggle') {
      this.trigger._handleClick = () => { };
      this.elementRef.nativeElement.addEventListener('click', () => this.trigger.toggleMenu());
    } else {
      this.elementRef.nativeElement.addEventListener('mouseenter', () => this.trigger.openMenu());
      this.elementRef.nativeElement.addEventListener('mouseleave', () => this.trigger.closeMenu());
    }
  }

  open(): void {
    this.trigger.openMenu();
  }

  close(): void {
    this.trigger.closeMenu();
  }
}