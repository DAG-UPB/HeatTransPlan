/** The page's own API key: fetched once, sent with every request, renewed
 *  when the server refuses it; the open endpoints go without. */

import axios, { type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type Seen = { url: string; key: string | undefined };

function server(refuse: (key: string | undefined) => boolean) {
  const seen: Seen[] = [];
  let issued = 0;
  const adapter: AxiosAdapter = async (cfg: InternalAxiosRequestConfig) => {
    const url = (cfg.url || '').replace(/^https?:\/\/[^/]+/, '');
    const key = cfg.headers?.get?.('X-API-Key') as string | undefined;
    seen.push({ url, key: key || undefined });
    const reply = (status: number, data: unknown) => {
      const res = { data, status, statusText: '', headers: {}, config: cfg };
      if (status >= 400) throw new axios.AxiosError('refused', String(status), cfg, null, res);
      return res;
    };
    if (url === '/api/keys/page') {
      issued += 1;
      return reply(200, { key: `page-${issued}`, expires_at: Date.now() / 1000 + 86400 });
    }
    // /api/features needs no key, like on the server.
    return url !== '/api/features' && refuse(key)
      ? reply(403, { detail: 'Missing or invalid API key' })
      : reply(200, { ok: true });
  };
  return { seen, adapter };
}

async function freshClient(adapter: AxiosAdapter) {
  vi.resetModules();
  localStorage.clear();
  axios.defaults.adapter = adapter;
  const mod = await import('./client');
  mod.default.defaults.adapter = adapter;
  return mod;
}

describe('page token', () => {
  beforeEach(() => localStorage.clear());

  it('is fetched once and sent with every request, not with the open ones', async () => {
    const { seen, adapter } = server((k) => !k);
    const { default: client } = await freshClient(adapter);
    await Promise.all([client.get('/api/a'), client.get('/api/b')]);
    await client.get('/api/features');
    expect(seen.filter((s) => s.url === '/api/keys/page')).toHaveLength(1);
    expect(seen.filter((s) => s.url.startsWith('/api/a') || s.url.startsWith('/api/b'))).toEqual([
      { url: '/api/a', key: 'page-1' },
      { url: '/api/b', key: 'page-1' },
    ]);
    expect(seen.find((s) => s.url === '/api/features')?.key).toBeUndefined();
  });

  it('is renewed once when the server refuses it', async () => {
    const { seen, adapter } = server((k) => k !== 'page-2');
    const { default: client } = await freshClient(adapter);
    const r = await client.get('/api/a');
    expect(r.status).toBe(200);
    expect(seen.map((s) => `${s.url}:${s.key ?? ''}`)).toEqual([
      '/api/keys/page:',
      '/api/a:page-1',
      '/api/keys/page:',
      '/api/a:page-2',
    ]);
  });

  it('gives up after one renewal', async () => {
    const { seen, adapter } = server(() => true);
    const { default: client } = await freshClient(adapter);
    await expect(client.get('/api/a')).rejects.toThrow();
    expect(seen.filter((s) => s.url === '/api/a')).toHaveLength(2);
  });

  it('is not sent where the server checks no keys', async () => {
    const seen: Seen[] = [];
    const adapter: AxiosAdapter = async (cfg) => {
      seen.push({
        url: cfg.url || '',
        key: (cfg.headers?.get?.('X-API-Key') as string) || undefined,
      });
      const data = (cfg.url || '').endsWith('/api/keys/page')
        ? { key: null, expires_at: null }
        : {};
      return { data, status: 200, statusText: '', headers: {}, config: cfg };
    };
    const { default: client, authHeaders } = await freshClient(adapter);
    await client.get('/api/a');
    await client.get('/api/b');
    expect(seen.filter((s) => s.url === '/api/keys/page')).toHaveLength(1);
    expect(seen.every((s) => !s.key)).toBe(true);
    expect(await authHeaders()).toEqual({});
  });
});
