/** The page's side of a live session: only it holds the page token, sends
 *  it on its own requests, shows the user's pause, and lets go when another
 *  tab takes the session over. */

import { describe, it, expect, beforeEach, vi } from 'vitest';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('../api/client', () => ({
  default: { ...api, interceptors: { request: { use: vi.fn() } } },
  API_BASE: '',
  authHeaders: async () => ({}),
}));

import { connectLive, disconnectLive, setAiPaused, useLiveStore } from './liveClient';

const SAVED = 'heattransplan_live_session';
const OWN = { headers: { 'X-Live-Page-Token': 'tok' } };

/** An event stream that sends these events, then waits until aborted. */
function stream(events: Array<[string, unknown]>, signal: AbortSignal) {
  const text = events.map(([t, d]) => `event: ${t}\ndata: ${JSON.stringify(d)}\n\n`).join('');
  return new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(new TextEncoder().encode(text));
      signal.addEventListener('abort', () => c.error(new DOMException('aborted', 'AbortError')));
    },
  });
}

const settle = () => new Promise((r) => setTimeout(r, 20));

beforeEach(() => {
  sessionStorage.clear();
  Object.values(api).forEach((f) => f.mockReset());
  api.post.mockResolvedValue({
    data: { session_id: 'abcd1234', project_id: 'p', page_token: 'tok', paused: false },
  });
  api.put.mockResolvedValue({ data: { paused: true } });
  api.delete.mockResolvedValue({});
  useLiveStore.setState({ status: 'off', sessionId: null, paused: false, log: [], error: null });
});

describe('live client', () => {
  it('keeps the page token to itself and sends it on its own requests', async () => {
    const fetch = vi.fn(async (_url: string, init: RequestInit) => ({
      ok: true,
      status: 200,
      body: stream(
        [
          ['hello', { paused: false }],
          ['paused', { paused: true }],
          ['command', { id: 'c1', name: 'set_project', args: { state: null } }],
        ],
        init.signal as AbortSignal
      ),
    }));
    vi.stubGlobal('fetch', fetch);
    await connectLive();
    await settle();

    expect(JSON.parse(sessionStorage.getItem(SAVED)!)).toEqual({
      session_id: 'abcd1234',
      page_token: 'tok',
    });
    expect(fetch.mock.calls[0][0]).toBe('/api/live/sessions/abcd1234/events');
    expect((fetch.mock.calls[0][1].headers as Record<string, string>)['X-Live-Page-Token']).toBe(
      'tok'
    );
    // The pause made on the server shows, and a command still on its way is refused.
    expect(useLiveStore.getState().paused).toBe(true);
    expect(api.post).toHaveBeenLastCalledWith(
      '/api/live/sessions/abcd1234/commands/c1/result',
      { ok: false, error: 'The user has paused the AI on this page.' },
      OWN
    );

    await setAiPaused(false);
    expect(api.put).toHaveBeenCalledWith(
      '/api/live/sessions/abcd1234/pause',
      { paused: false },
      OWN
    );
    await disconnectLive();
    expect(api.delete).toHaveBeenCalledWith('/api/live/sessions/abcd1234', OWN);
    expect(sessionStorage.getItem(SAVED)).toBeNull();
    vi.unstubAllGlobals();
  });

  it('reconnects after a reload with the saved token, and lets go when another tab takes over', async () => {
    sessionStorage.setItem(SAVED, JSON.stringify({ session_id: 'abcd1234', page_token: 'tok' }));
    api.get.mockResolvedValue({ data: { session_id: 'abcd1234', project_id: 'p', paused: false } });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => ({
        ok: true,
        status: 200,
        body: stream(
          [
            ['hello', {}],
            ['replaced', {}],
          ],
          init.signal as AbortSignal
        ),
      }))
    );
    await connectLive();
    await settle();
    expect(api.get).toHaveBeenCalledWith('/api/live/sessions/abcd1234', OWN);
    expect(api.post).not.toHaveBeenCalled();
    expect(useLiveStore.getState().status).toBe('error');
    expect(useLiveStore.getState().error).toMatch(/another tab/);
    expect(sessionStorage.getItem(SAVED)).toBeNull();
    vi.unstubAllGlobals();
  });
});
