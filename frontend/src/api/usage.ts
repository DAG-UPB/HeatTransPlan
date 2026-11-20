/** Anonymous usage counting (backend app/services/usage.py): which page is
 *  open and a few clicks, by name only. Fire and forget: a lost count never
 *  bothers the visitor. Nothing is stored in the browser for it. */

import client from './client';

export type UsageEvent =
  | 'page:home'
  | 'page:data-collection'
  | 'page:potential-analysis'
  | 'ui:try_example'
  | 'ui:tour'
  | 'ui:page_tour'
  | 'ui:language'
  | 'ui:project_open'
  | 'ui:project_save';

const PAGES: Record<string, UsageEvent> = {
  '/': 'page:home',
  '/data-collection': 'page:data-collection',
  '/potential-analysis': 'page:potential-analysis',
};

export function track(name: UsageEvent): void {
  if (import.meta.env.MODE === 'test') return;
  client.post('/api/usage/event', { name }).catch(() => undefined);
}

export function trackPage(pathname: string): void {
  const name = PAGES[pathname];
  if (name) track(name);
}
