import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-settings-notifications-section',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './settings-notifications-section.component.html',
  styleUrl: '../settings-shared.scss',
})
export class SettingsNotificationsSectionComponent {
  pushEnabled = input.required<boolean>();
  emailEnabled = input.required<boolean>();
  pushChange = output<boolean>();
  emailChange = output<boolean>();

  onPushChange() {
    this.pushChange.emit(true);
  }

  onEmailChange() {
    this.emailChange.emit(true);
  }
}
