import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export interface LogContext {
  [key: string]: unknown;
}

@Injectable({
  providedIn: 'root',
})
export class LoggerService {
  private http = inject(HttpClient);
  private buffer: Array<{ level: LogLevel; message: string; context?: LogContext; timestamp: string }> = [];
  private flushIntervalMs = 10000;
  private flushTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    const sendToBackend = (environment as { sendLogsToBackend?: boolean }).sendLogsToBackend === true;
    if (sendToBackend && typeof setInterval !== 'undefined') {
      this.flushTimer = setInterval(() => this.flush(), this.flushIntervalMs);
    }
  }

  private getLevel(): LogLevel {
    return (environment as { logLevel?: LogLevel }).logLevel ?? 'debug';
  }

  private shouldLog(level: LogLevel): boolean {
    const current = LEVEL_ORDER[this.getLevel()];
    const messageLevel = LEVEL_ORDER[level];
    return messageLevel >= current;
  }

  private log(level: LogLevel, message: string, context?: LogContext): void {
    if (!this.shouldLog(level)) return;

    const timestamp = new Date().toISOString();
    const payload = { level, message, context, timestamp };

    switch (level) {
      case 'debug':
        if (typeof console !== 'undefined' && console.debug) {
          console.debug(`[Parkpe ${level}]`, message, context ?? '');
        }
        break;
      case 'info':
        if (typeof console !== 'undefined' && console.info) {
          console.info(`[Parkpe ${level}]`, message, context ?? '');
        }
        break;
      case 'warn':
        if (typeof console !== 'undefined' && console.warn) {
          console.warn(`[Parkpe ${level}]`, message, context ?? '');
        }
        break;
      case 'error':
        if (typeof console !== 'undefined' && console.error) {
          console.error(`[Parkpe ${level}]`, message, context ?? '');
        }
        break;
    }

    const sendToBackend = (environment as { sendLogsToBackend?: boolean }).sendLogsToBackend === true;
    if (sendToBackend) {
      this.buffer.push(payload);
      if (level === 'error') this.flush();
    }
  }

  debug(message: string, context?: LogContext): void {
    this.log('debug', message, context);
  }

  info(message: string, context?: LogContext): void {
    this.log('info', message, context);
  }

  warn(message: string, context?: LogContext): void {
    this.log('warn', message, context);
  }

  error(message: string, context?: LogContext): void {
    this.log('error', message, context);
  }

  private flush(): void {
    if (this.buffer.length === 0) return;
    const apiUrl = environment.apiUrl ?? '';
    if (!apiUrl) return;

    const events = this.buffer.map((e) => ({
      type: 'frontend_log',
      level: e.level,
      message: e.message,
      context: e.context,
      timestamp: e.timestamp,
    }));
    this.buffer = [];

    this.http
      .post(`${apiUrl.replace(/\/$/, '')}/v1/logging/bulk/`, { events })
      .subscribe({
        error: () => {
          if (typeof console !== 'undefined' && console.warn) {
            console.warn('[Parkpe] Failed to send logs to backend');
          }
        },
      });
  }
}
