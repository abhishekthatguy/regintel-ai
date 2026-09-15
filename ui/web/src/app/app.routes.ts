import { Routes } from '@angular/router';
import { AnalyticsComponent } from './analytics.component';
import { ChatComponent } from './chat.component';

export const routes: Routes = [
  { path: '', component: ChatComponent },
  { path: 'analytics', component: AnalyticsComponent },
];
