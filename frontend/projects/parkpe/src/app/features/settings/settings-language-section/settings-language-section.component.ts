import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export interface LanguageOption {
  code: string;
  label: string;
}

@Component({
  selector: 'app-settings-language-section',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './settings-language-section.component.html',
  styleUrl: '../settings-shared.scss',
})
export class SettingsLanguageSectionComponent {
  selectedLanguage = input.required<string>();
  supportedLanguages = input.required<LanguageOption[]>();
  languageChange = output<string>();
}
