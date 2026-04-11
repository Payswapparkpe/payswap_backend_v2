import { Injectable } from '@angular/core';
import { Route, PreloadingStrategy } from '@angular/router';
import { Observable, of, timer } from 'rxjs';
import { switchMap } from 'rxjs/operators';

type PreloadHint = {
  enabled?: boolean;
  priority?: number;
};

@Injectable({ providedIn: 'root' })
export class PriorityPreloadingStrategy implements PreloadingStrategy {
  preload(route: Route, load: () => Observable<unknown>): Observable<unknown> {
    const hint = (route.data?.['preload'] as PreloadHint | boolean | undefined) ?? false;
    const resolved = this.resolveHint(hint);
    if (!resolved.enabled) return of(null);

    // Stagger low-priority chunks so initial mobile navigation stays responsive.
    const delayMs = Math.max(0, (resolved.priority - 1) * 1200);
    return timer(delayMs).pipe(switchMap(() => load()));
  }

  private resolveHint(hint: PreloadHint | boolean): Required<PreloadHint> {
    if (typeof hint === 'boolean') {
      return { enabled: hint, priority: hint ? 3 : 99 };
    }
    return {
      enabled: hint.enabled ?? true,
      priority: hint.priority ?? 3,
    };
  }
}
