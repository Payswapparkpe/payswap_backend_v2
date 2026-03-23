import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import type { User } from 'shared';

@Component({
  selector: 'app-settings-account-section',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './settings-account-section.component.html',
  styleUrl: '../settings-shared.scss',
})
export class SettingsAccountSectionComponent {
  user = input<User | null>(null);
  logoutClick = output<void>();

  logout() {
    this.logoutClick.emit();
  }
}
