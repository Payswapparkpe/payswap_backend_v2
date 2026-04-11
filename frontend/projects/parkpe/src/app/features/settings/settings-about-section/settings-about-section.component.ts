import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-settings-about-section',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './settings-about-section.component.html',
  styleUrl: '../settings-shared.scss',
})
export class SettingsAboutSectionComponent {
  appVersion = input.required<string>();
  useMockApi = input.required<boolean>();
}
