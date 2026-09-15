import { Injectable, signal } from '@angular/core';

const API_BASE = 'http://localhost:8000';

export interface Citation {
  citation_id: string;
  document_id: string;
  title: string;
  source_system: string;
  source_ref: string | null;
  page_section: string | null;
  chunk_id: string | null;
  excerpt: string | null;
  retrieval_score: number | null;
  rerank_score: number | null;
  document_version: string | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  messageId?: string;
  usage?: Record<string, unknown>;
  feedback?: 'up' | 'down';
}

interface StreamEvent {
  type: 'status' | 'token' | 'citation' | 'usage' | 'complete' | 'error';
  data: Record<string, unknown> & { detail?: string; stage?: string; text?: string };
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  /** Demo identity — stub mode uses the header; JWT mode uses the bearer
      token (mint dev tokens via scripts/mint_dev_token.py). */
  employee = signal('e001');
  bearerToken = signal('');

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      'X-Demo-Employee': this.employee(),
      'Content-Type': 'application/json',
    };
    if (this.bearerToken()) h['Authorization'] = `Bearer ${this.bearerToken()}`;
    return h;
  }

  async listConversations(): Promise<Record<string, string>[]> {
    const r = await fetch(`${API_BASE}/v1/conversations`, { headers: this.headers() });
    if (!r.ok) throw new Error(`list failed: ${r.status}`);
    return r.json();
  }

  async createConversation(usecaseId: string): Promise<{ conversation_id: string }> {
    const r = await fetch(`${API_BASE}/v1/conversations`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ usecase_id: usecaseId }),
    });
    if (!r.ok) throw new Error(`create failed: ${r.status}`);
    return r.json();
  }

  async getConversation(id: string): Promise<Record<string, unknown>> {
    const r = await fetch(`${API_BASE}/v1/conversations/${id}`, { headers: this.headers() });
    if (!r.ok) throw new Error(`load failed: ${r.status}`);
    return r.json();
  }

  async renameConversation(id: string, title: string): Promise<void> {
    await fetch(`${API_BASE}/v1/conversations/${id}`, {
      method: 'PATCH',
      headers: this.headers(),
      body: JSON.stringify({ title }),
    });
  }

  async sendFeedback(messageId: string, rating: 'up' | 'down'): Promise<void> {
    await fetch(`${API_BASE}/v1/messages/${messageId}/feedback`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ rating }),
    });
  }

  async analytics(): Promise<Record<string, unknown>> {
    const r = await fetch(`${API_BASE}/v1/admin/analytics`, { headers: this.headers() });
    if (!r.ok) throw new Error(`analytics failed: ${r.status}`);
    return r.json();
  }

  /** NDJSON stream — yields parsed events as they arrive. */
  async *streamMessage(
    conversationId: string,
    content: string,
    language = 'en',
  ): AsyncGenerator<StreamEvent> {
    const r = await fetch(`${API_BASE}/v1/conversations/${conversationId}/messages:stream`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ content, language }),
    });
    if (!r.ok || !r.body) throw new Error(`stream failed: ${r.status}`);

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (line.trim()) yield JSON.parse(line) as StreamEvent;
      }
    }
  }
}
