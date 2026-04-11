import { Component, inject, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  ConnectService,
  ConnectThreadDto,
  ConnectPredefinedMessageDto,
} from '../services/connect.service';
import { ConnectChatService } from '../services/connect-chat.service';
import { AuthService } from '@core/services/auth.service';

@Component({
  selector: 'app-connect-thread-chat',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-thread-chat.component.html',
  styleUrl: './connect-thread-chat.component.scss',
})
export class ConnectThreadChatComponent implements OnInit, OnDestroy {
  private connect = inject(ConnectService);
  public chatService = inject(ConnectChatService); // Public for HTML
  private route = inject(ActivatedRoute);
  private auth = inject(AuthService);

  thread = signal<ConnectThreadDto | null>(null);
  predefined = signal<ConnectPredefinedMessageDto[]>([]);
  messageInput = signal('');

  // Local loading for thread details (messages are loaded by chatService)
  threadLoading = signal(true);
  threadError = signal<string | null>(null);

  showReportModal = signal(false);
  reportReason = signal('');
  reportSubmitting = signal(false);
  reportError = signal<string | null>(null);

  currentUserId = computed(() => {
    const u = this.auth.userSignal();
    const id = u?.id;
    return id != null ? Number(id) : null;
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('threadId');
    const tid = id ? parseInt(id, 10) : NaN;
    if (!id || isNaN(tid)) {
      this.threadError.set('Invalid thread');
      this.threadLoading.set(false);
      return;
    }

    // Load Thread Details (Header info)
    this.connect.getThread(tid).subscribe({
      next: (t) => {
        this.thread.set(t);
        this.threadLoading.set(false);

        // Initialize Chat Service
        this.chatService.loadThread(t.id, t.other_participant_id ?? null);

        // Load predefined
        this.connect.getPredefinedMessages().subscribe({
          next: (list) => this.predefined.set(list),
          error: () => { },
        });
      },
      error: (err) => {
        this.threadError.set(err?.error?.detail || 'Thread not found');
        this.threadLoading.set(false);
      },
    });
  }

  onMessageInput(e: Event) {
    this.messageInput.set((e.target as HTMLInputElement)?.value ?? '');
  }

  sendMessage() {
    const body = this.messageInput().trim();
    if (!body) return;
    this.chatService.sendMessage(body);
    this.messageInput.set('');
  }

  sendPredefined(code: string) {
    this.chatService.sendMessage('', true, code);
  }

  openReportModal() {
    this.reportReason.set('');
    this.reportError.set(null);
    this.showReportModal.set(true);
  }

  closeReportModal() {
    this.showReportModal.set(false);
    this.reportError.set(null);
  }

  onReportReasonInput(e: Event) {
    this.reportReason.set((e.target as HTMLTextAreaElement)?.value ?? '');
  }

  submitReport() {
    const t = this.thread();
    const otherId = t?.other_participant_id;
    const reason = this.reportReason().trim();
    if (!t || otherId == null || !reason) return;
    this.reportSubmitting.set(true);
    this.reportError.set(null);
    this.connect.reportUser(t.id, otherId, reason).subscribe({
      next: () => {
        this.reportSubmitting.set(false);
        this.closeReportModal();
      },
      error: (err) => {
        this.reportSubmitting.set(false);
        this.reportError.set(err?.error?.detail || 'Failed to submit report.');
      },
    });
  }

  ngOnDestroy() {
    this.chatService.clearThread();
  }
}
