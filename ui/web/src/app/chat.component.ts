import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, ChatMessage } from './api.service';

// Web Speech API isn't in the TS DOM lib — minimal local types.
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: { [k: number]: { [k: number]: { transcript: string } } } }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
})
export class ChatComponent implements OnInit {
  protected api = inject(ApiService);

  usecaseId = 'it_support';
  language = 'en';
  languages = ['en', 'hi', 'es', 'fr'];
  conversationId = signal<string | null>(null);
  conversations = signal<Record<string, string>[]>([]);
  messages = signal<ChatMessage[]>([]);
  nodeTrace = signal<string[]>([]);
  busy = signal(false);
  error = signal('');
  draft = '';
  listening = signal(false);
  voiceSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
  ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  private recognition: SpeechRecognitionLike | null = null;

  async ngOnInit() {
    await this.refreshConversations();
  }

  async refreshConversations() {
    try {
      this.conversations.set(await this.api.listConversations());
    } catch {
      this.conversations.set([]);
    }
  }

  async newConversation() {
    this.conversationId.set(null);
    this.messages.set([]);
    this.nodeTrace.set([]);
    this.error.set('');
  }

  async resume(id: string) {
    this.conversationId.set(id);
    const detail = await this.api.getConversation(id);
    const msgs = (detail['messages'] as Record<string, unknown>[]) ?? [];
    this.messages.set(
      msgs.map((m) => ({
        role: m['role'] as 'user' | 'assistant',
        content: m['content'] as string,
        citations: (m['citations'] as never) ?? [],
        messageId: m['message_id'] as string,
      })),
    );
  }

  async rename() {
    const id = this.conversationId();
    if (!id) return;
    const title = prompt('Rename conversation:');
    if (title) {
      await this.api.renameConversation(id, title);
      await this.refreshConversations();
    }
  }

  async send() {
    const content = this.draft.trim();
    if (!content || this.busy()) return;
    this.draft = '';
    this.error.set('');
    this.busy.set(true);
    this.nodeTrace.set([]);

    try {
      if (!this.conversationId()) {
        const conv = await this.api.createConversation(this.usecaseId);
        this.conversationId.set(conv.conversation_id);
      }
      const convId = this.conversationId()!;
      const reply: ChatMessage = { role: 'assistant', content: '', citations: [] };
      this.messages.update((m) => [
        ...m,
        { role: 'user', content, citations: [] },
        reply,
      ]);

      for await (const ev of this.api.streamMessage(convId, content, this.language)) {
        if (ev.type === 'status' && ev.data['stage'] === 'node') {
          this.nodeTrace.update((n) => [...n, String(ev.data['detail'])]);
        } else if (ev.type === 'token') {
          reply.content += String(ev.data['text'] ?? '');
          this.messages.update((m) => [...m]);
        } else if (ev.type === 'citation') {
          reply.citations.push(ev.data as never);
        } else if (ev.type === 'usage') {
          reply.usage = ev.data;
        } else if (ev.type === 'complete') {
          reply.messageId = String(ev.data['message_id']);
        } else if (ev.type === 'error') {
          this.error.set(String(ev.data['message'] ?? 'stream error'));
        }
      }
      await this.refreshConversations();
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'request failed');
    } finally {
      this.busy.set(false);
    }
  }

  toggleMic() {
    if (!this.voiceSupported) return;
    if (this.listening()) {
      this.recognition?.stop();
      return;
    }
    const w = window as unknown as {
      SpeechRecognition?: SpeechRecognitionCtor;
      webkitSpeechRecognition?: SpeechRecognitionCtor;
    };
    const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    this.recognition = rec;
    rec.lang = this.language === 'en' ? 'en-US' : this.language;
    rec.interimResults = false;
    rec.onresult = (e) => {
      // Transcript is the source of truth — flows through the same text pipeline.
      this.draft = e.results[0][0].transcript;
      this.listening.set(false);
    };
    rec.onerror = () => this.listening.set(false);
    rec.onend = () => this.listening.set(false);
    rec.start();
    this.listening.set(true);
  }

  speak(msg: ChatMessage) {
    if (!this.ttsSupported || !msg.content) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(msg.content);
    u.lang = this.language === 'en' ? 'en-US' : this.language;
    speechSynthesis.speak(u);
  }

  async feedback(msg: ChatMessage, rating: 'up' | 'down') {
    if (!msg.messageId) return;
    await this.api.sendFeedback(msg.messageId, rating);
    msg.feedback = rating;
    this.messages.update((m) => [...m]);
  }
}
