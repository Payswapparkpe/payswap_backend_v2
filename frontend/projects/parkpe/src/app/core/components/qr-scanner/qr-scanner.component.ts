import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';

/**
 * Optimised QR scanner for parking / gate flows — GPU decode path + optional low-light boost.
 */
@Component({
  selector: 'app-qr-scanner',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './qr-scanner.component.html',
  styleUrl: './qr-scanner.component.scss',
})
export class QrScannerComponent implements AfterViewInit, OnDestroy {
  readonly containerId = input(`park-qr-${Math.random().toString(36).slice(2, 9)}`);
  readonly fps = input(15);
  readonly scanSuccess = output<string>();
  readonly scanError = output<unknown>();

  lowLight = signal(false);

  private host = viewChild<ElementRef<HTMLElement>>('host');
  private scanner: import('html5-qrcode').Html5Qrcode | null = null;
  private Html5QrcodeClass: typeof import('html5-qrcode').Html5Qrcode | null = null;

  ngAfterViewInit(): void {
    void this.start();
  }

  ngOnDestroy(): void {
    void this.stop();
  }

  toggleLowLight(): void {
    this.lowLight.update((v) => !v);
  }

  private async start(): Promise<void> {
    const el = this.host()?.nativeElement;
    if (!el) return;
    try {
      const mod = await import('html5-qrcode');
      this.Html5QrcodeClass = mod.Html5Qrcode;
    } catch (e) {
      this.scanError.emit(e);
      return;
    }
    if (!this.Html5QrcodeClass) return;

    const regionId = this.containerId();
    this.scanner = new this.Html5QrcodeClass(regionId, {
      experimentalFeatures: { useBarCodeDetectorIfSupported: true },
    });

    try {
      await this.scanner.start(
        { facingMode: 'environment' },
        {
          fps: this.fps(),
          qrbox: { width: 250, height: 250 },
          aspectRatio: 1,
        },
        (decoded) => {
          if (decoded && typeof decoded === 'string') {
            try {
              navigator.vibrate?.(40);
            } catch {
              /* ignore */
            }
            this.scanSuccess.emit(decoded);
          }
        },
        () => {
          /* frame decode miss — ignore */
        }
      );
    } catch (e) {
      this.scanError.emit(e);
    }
  }

  private async stop(): Promise<void> {
    if (!this.scanner) return;
    try {
      await this.scanner.stop();
      await this.scanner.clear();
    } catch {
      /* ignore */
    }
    this.scanner = null;
  }
}
