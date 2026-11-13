/** The HTTP client for the backend. When the server checks API keys, the page
 *  gets its own short-lived token (POST /api/keys/page, about a day) and sends
 *  it with every request; the visitor never sees it. Nothing is baked into
 *  the bundle: VITE_API_KEY is for local development only. */

import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE || '';
/** A fixed key for development; production pages fetch a page token. */
const FIXED_KEY: string = import.meta.env.VITE_API_KEY || '';

/** What the server answers without a key. */
const OPEN = /^\/api\/(health|features|keys(\/page)?)$|^\/api\/mcp\/files\//;
const STORE = 'heattransplan.pageToken';

interface Token {
  key: string | null;
  /** Unix time; with key null: when to ask again whether keys are on. */
  exp: number;
}

// In this browser (localStorage), so all its tabs share one token a day.
function load(): Token | null {
  try {
    const t = JSON.parse(localStorage.getItem(STORE) || 'null');
    return t && typeof t.exp === 'number' ? t : null;
  } catch {
    return null;
  }
}

function save(t: Token) {
  try {
    localStorage.setItem(STORE, JSON.stringify(t));
  } catch {
    /* private mode or blocked storage: memory only */
  }
}

let token: Token | null = load();
let pending: Promise<string | null> | null = null;

/** The key this page sends, or null when the server checks none. */
export async function pageKey(fresh = false): Promise<string | null> {
  if (FIXED_KEY) return FIXED_KEY;
  // Renewed five minutes before it runs out.
  if (!fresh && token && token.exp - 300 > Date.now() / 1000) return token.key;
  pending ??= axios
    .post<{ key: string | null; expires_at: number | null }>(`${API_BASE}/api/keys/page`)
    .then((r) => {
      const key = r.data?.key ?? null;
      // Keys off on this server: ask again in an hour, in case that changes.
      const exp = key && r.data.expires_at ? r.data.expires_at : Date.now() / 1000 + 3600;
      token = { key, exp };
      save(token);
      return key;
    })
    .finally(() => {
      pending = null;
    });
  return pending;
}

/** Headers for a request made without this client (the live event stream). */
export async function authHeaders(fresh = false): Promise<Record<string, string>> {
  const key = await pageKey(fresh);
  return key ? { 'X-API-Key': key } : {};
}

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use(async (cfg) => {
  if (!OPEN.test(cfg.url || '')) {
    const key = await pageKey();
    if (key) cfg.headers.set('X-API-Key', key);
  }
  return cfg;
});

// Refused (token expired, secret changed): a fresh token, then once more.
client.interceptors.response.use(undefined, async (err: AxiosError) => {
  const cfg = err.config as (InternalAxiosRequestConfig & { _keyRetry?: boolean }) | undefined;
  const status = err.response?.status;
  if (
    cfg &&
    !cfg._keyRetry &&
    !FIXED_KEY &&
    (status === 401 || status === 403) &&
    !OPEN.test(cfg.url || '')
  ) {
    cfg._keyRetry = true;
    const key = await pageKey(true);
    if (key) {
      cfg.headers.set('X-API-Key', key);
      return client(cfg);
    }
  }
  throw err;
});

export default client;
