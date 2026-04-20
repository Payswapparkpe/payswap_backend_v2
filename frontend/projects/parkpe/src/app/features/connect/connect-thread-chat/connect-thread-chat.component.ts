import { Component, inject, OnInit, OnDestroy, signal, computed, ViewChild, ElementRef } from '@angular/core';
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
  messageSearch = signal('');
  /** Inline chat search (hidden until opened — like Telegram). */
  showMessageSearch = signal(false);
  messageSearchPanelOpen = computed(() => this.showMessageSearch() || this.messageSearch().trim().length > 0);
  showArchivedMutedHint = signal(false);
  recording = signal(false);
  recordingSeconds = signal(0);
  private mediaRecorder: MediaRecorder | null = null;
  private mediaChunks: Blob[] = [];
  private recordingTimer: ReturnType<typeof setInterval> | null = null;
  private recordStartedAt = 0;
  @ViewChild('attachmentInput') attachmentInput?: ElementRef<HTMLInputElement>;

  // Local loading for thread details (messages are loaded by chatService)
  threadLoading = signal(true);
  threadError = signal<string | null>(null);

  showReportModal = signal(false);
  reportReason = signal('');
  reportSubmitting = signal(false);
  reportError = signal<string | null>(null);
  blockInProgress = signal(false);

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
        this.showArchivedMutedHint.set(!!(t.archived || t.muted));
        this.loadDraft(t.id);

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
    this.chatService.notifyTyping(true);
    this.saveDraft();
  }

  sendMessage() {
    const body = this.messageInput().trim();
    if (!body) return;
    this.chatService.sendMessage(body);
    this.messageInput.set('');
    this.saveDraft();
  }

  sendPredefined(code: string) {
    this.chatService.sendMessage('', true, code);
  }

  prefLabel(pref: ConnectPredefinedMessageDto): string {
    const lang = (navigator.language || '').toLowerCase();
    if (lang.startsWith('hi') && pref.label_hi?.trim()) {
      return pref.label_hi;
    }
    return pref.label_en;
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

  onComposerKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.sendMessage();
    }
  }

  onSearchInput(e: Event) {
    this.messageSearch.set((e.target as HTMLInputElement)?.value ?? '');
  }

  toggleMessageSearch() {
    this.showMessageSearch.update((v) => !v);
  }

  clearMessageSearch() {
    this.messageSearch.set('');
  }

  filteredMessages = computed(() => {
    const q = this.messageSearch().trim().toLowerCase();
    const messages = this.chatService.messages();
    if (!q) return messages;
    return messages.filter((m) => {
      const text = `${m.body} ${(m.metadata?.['file_name'] || '')}`.toLowerCase();
      return text.includes(q);
    });
  });

  /** A11y label for delivery ticks (own messages). */
  deliveryLabel(msg: { delivery_status?: string; local_failed?: boolean }): string {
    if (msg.local_failed || msg.delivery_status === 'failed') return 'Failed to send';
    const s = (msg.delivery_status || 'sent').toLowerCase();
    if (s === 'sending') return 'Sending';
    if (s === 'delivered') return 'Delivered';
    if (s === 'seen') return 'Read';
    return 'Sent';
  }

  /** Telegram-style tick row for outgoing bubbles. */
  tickKind(msg: { delivery_status?: string; local_failed?: boolean }): 'failed' | 'sending' | 'sent' | 'delivered' | 'read' {
    if (msg.local_failed || msg.delivery_status === 'failed') return 'failed';
    const s = (msg.delivery_status || 'sent').toLowerCase();
    if (s === 'sending') return 'sending';
    if (s === 'seen') return 'read';
    if (s === 'delivered') return 'delivered';
    return 'sent';
  }

  /** Chat title second part: always the person you're messaging (scanner ↔ owner). */
  peerDisplayName(t: ConnectThreadDto): string {
    const p = (t.peer_display_name || '').trim();
    if (p) return p;
    return (t.owner_display_name || '').replace(/\*+$/, '').trim() || '?';
  }

  threadSubtitle(t: ConnectThreadDto): string {
    return t.is_owner ? 'You are the vehicle owner' : 'You opened this chat from the vehicle QR';
  }

  avatarInitial(t: ConnectThreadDto): string {
    const name = (t.peer_display_name || t.owner_display_name || '').trim().replace(/\*+$/, '');
    const reg = (t.registration_number_masked || '').trim();
    const s = name || reg;
    if (!s) return '?';
    return s.charAt(0).toUpperCase();
  }

  retryMessage(messageId: number) {
    this.chatService.retryFailedMessage(messageId);
  }

  triggerAttachmentPicker() {
    this.attachmentInput?.nativeElement?.click();
  }

  onAttachmentPicked(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input?.files?.[0];
    if (!file) return;
    this.chatService.sendAttachment(file);
    input.value = '';
  }

  async toggleVoiceRecording() {
    if (this.recording()) {
      this.stopVoiceRecording();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaChunks = [];
      this.recordStartedAt = Date.now();
      this.mediaRecorder = new MediaRecorder(stream);
      this.mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) this.mediaChunks.push(ev.data);
      };
      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.mediaChunks, { type: this.mediaRecorder?.mimeType || 'audio/webm' });
        const sec = Math.max(1, Math.round((Date.now() - this.recordStartedAt) / 1000));
        this.chatService.sendVoiceNote(blob, sec);
        stream.getTracks().forEach((t) => t.stop());
      };
      this.mediaRecorder.start();
      this.recording.set(true);
      this.recordingSeconds.set(0);
      this.recordingTimer = setInterval(() => this.recordingSeconds.update((v) => v + 1), 1000);
    } catch {
      this.chatService.setError('Microphone permission denied.');
    }
  }

  stopVoiceRecording() {
    if (!this.mediaRecorder) return;
    if (this.recordingTimer) {
      clearInterval(this.recordingTimer);
      this.recordingTimer = null;
    }
    if (this.mediaRecorder.state !== 'inactive') this.mediaRecorder.stop();
    this.recording.set(false);
    this.mediaRecorder = null;
  }

  toggleThreadSetting(setting: 'pinned' | 'muted' | 'archived') {
    const t = this.thread();
    if (!t) return;
    const nextVal = !Boolean(t[setting]);
    this.connect.updateThreadSettings(t.id, { [setting]: nextVal }).subscribe({
      next: (updated) => this.thread.set({ ...t, ...updated }),
      error: () => {},
    });
  }

  blockOrUnblockUser() {
    const t = this.thread();
    if (!t || this.blockInProgress()) return;
    this.blockInProgress.set(true);
    const action: 'block' | 'unblock' = t.muted ? 'unblock' : 'block';
    this.connect.blockThreadParticipant(t.id, action).subscribe({
      next: () => {
        this.blockInProgress.set(false);
        this.thread.set({ ...t, muted: action === 'block' ? true : false });
      },
      error: () => {
        this.blockInProgress.set(false);
      },
    });
  }

  private saveDraft() {
    const t = this.thread();
    if (!t || typeof localStorage === 'undefined') return;
    localStorage.setItem(`connect:chat:draft:${t.id}`, this.messageInput());
  }

  private loadDraft(threadId: number) {
    if (typeof localStorage === 'undefined') return;
    const draft = localStorage.getItem(`connect:chat:draft:${threadId}`);
    this.messageInput.set(draft ?? '');
  }

  ngOnDestroy() {
    this.chatService.clearThread();
    if (this.recordingTimer) clearInterval(this.recordingTimer);
    if (this.recording()) this.stopVoiceRecording();
  }
}
