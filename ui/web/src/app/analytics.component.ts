import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ApiService } from './api.service';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analytics.component.html',
})
export class AnalyticsComponent implements OnInit {
  protected api = inject(ApiService);
  data = signal<Record<string, unknown> | null>(null);
  error = signal('');

  async ngOnInit() {
    try {
      this.data.set(await this.api.analytics());
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'failed — admin role required');
    }
  }

  get summary(): Record<string, unknown> {
    return (this.data()?.['summary'] as Record<string, unknown>) ?? {};
  }
  get byUsecase(): Record<string, unknown>[] {
    return (this.data()?.['by_usecase'] as Record<string, unknown>[]) ?? [];
  }
  get notFound(): Record<string, unknown>[] {
    return (this.data()?.['not_found_queries'] as Record<string, unknown>[]) ?? [];
  }
  get recentFeedback(): Record<string, unknown>[] {
    return (this.data()?.['recent_feedback'] as Record<string, unknown>[]) ?? [];
  }
  get byDepartment(): Record<string, unknown>[] {
    return (this.data()?.['by_department'] as Record<string, unknown>[]) ?? [];
  }
  get funnel(): Record<string, unknown> {
    return (this.data()?.['funnel'] as Record<string, unknown>) ?? {};
  }
  get unmetNeeds(): Record<string, unknown>[] {
    return (this.data()?.['unmet_needs'] as Record<string, unknown>[]) ?? [];
  }
}
