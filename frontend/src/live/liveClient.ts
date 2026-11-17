/** Connects the page to a live session on the backend, so an AI can watch and
 *  drive it (see backend/app/services/live.py).
 *
 *  Off until the user switches it on. Nothing of the project is kept on the
 *  server: the page holds the only copy. While connected the page runs the
 *  commands the AI sends (reading the project or what the page shows,
 *  applying an edit, ...) and answers each one; before one that deletes or
 *  replaces it asks the user (runAiCommand).
 *
 *  The session code is what the AI addresses the page by. The page's own key
 *  to its session is the page token, which only this tab gets: only it can
 *  listen, answer, pause, resume and end. It is kept in sessionStorage so a
 *  reload of this tab keeps the session. */

import { create } from 'zustand';
import client, { API_BASE, authHeaders } from '../api/client';
import { runAiCommand } from './commands';

type Status = 'off' | 'connecting' | 'on' | 'error';

/** One thing the AI changed, as the server noted it. */
export interface AiLogEntry {
  time: number;
  tool: string;
  detail: string;
}

interface LiveState {
  status: Status;
  sessionId: string | null;
  projectId: string | null;
  error: string | null;
  /** The user paused the AI: it can do nothing until resumed. */
  paused: boolean;
  /** What the AI changed, newest last. */
  log: AiLogEntry[];
}

const LOG_LENGTH = 50;
/** The header that shows a request comes from the page that owns the session. */
export const PAGE_TOKEN_HEADER = 'X-Live-Page-Token';

export const useLiveStore = create<LiveState>(() => ({
  status: 'off',
  sessionId: null,
  projectId: null,
  error: null,
  paused: false,
  log: [],
}));

const SAVED = 'heattransplan_live_session';
/** The server's answer to a token that is not the session's (routers/live.py). */
const NOT_OURS = 'Only the page that opened this session';

interface Saved {
  session_id: string;
  page_token: string;
}

let abort: AbortController | null = null;
let pageToken: string | null = null;
// AI commands running now: the server's activity log (X-Actor) tells the
// requests they make from the user's.
let aiCommands = 0;
client.interceptors.request.use((cfg) => {
  if (aiCommands > 0 && !cfg.headers['X-Actor']) cfg.headers['X-Actor'] = 'ai';
  return cfg;
});

const set = (patch: Partial<LiveState>) => useLiveStore.setState(patch);
const own = () => ({ headers: { [PAGE_TOKEN_HEADER]: pageToken ?? '' } });

function loadSaved(): Saved | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(SAVED) ?? 'null') as Saved | null;
    return saved?.session_id && saved.page_token ? saved : null;
  } catch {
    return null;
  }
}

function forgetSaved() {
  try {
    sessionStorage.removeItem(SAVED);
  } catch {
    // Storage blocked: nothing was kept.
  }
}

async function openSession(): Promise<{
  session_id: string;
  project_id: string;
  page_token: string;
  paused?: boolean;
}> {
  // A reload of the same tab keeps its session, and with it the AI's link.
  const saved = loadSaved();
  if (saved) {
    try {
      const { data } = await client.get(`/api/live/sessions/${saved.session_id}`, {
        headers: { [PAGE_TOKEN_HEADER]: saved.page_token },
      });
      return { ...data, page_token: saved.page_token };
    } catch {
      forgetSaved();
    }
  }
  const { data } = await client.post('/api/live/sessions');
  return data;
}

async function answer(sessionId: string, id: string, body: Record<string, unknown>) {
  try {
    await client.post(`/api/live/sessions/${sessionId}/commands/${id}/result`, body, own());
  } catch {
    // The AI stopped waiting; nothing to do.
  }
}

class Ended extends Error {}

function handleEvent(sessionId: string, type: string, data: Record<string, unknown>) {
  if (type === 'hello') set({ status: 'on', error: null, paused: Boolean(data.paused) });
  else if (type === 'paused') set({ paused: Boolean(data.paused) });
  else if (type === 'replaced') throw new Ended('This AI session is now open in another tab.');
  else if (type === 'ended') throw new Ended('The live session has ended.');
  else if (type === 'ai_log') {
    const entry = data as unknown as AiLogEntry;
    set({ log: [...useLiveStore.getState().log, entry].slice(-LOG_LENGTH) });
  } else if (type === 'command') {
    const id = String(data.id);
    // The server holds commands back while paused; one already on its way is refused too.
    if (useLiveStore.getState().paused) {
      void answer(sessionId, id, { ok: false, error: 'The user has paused the AI on this page.' });
      return;
    }
    aiCommands++;
    Promise.resolve()
      .then(() => runAiCommand(String(data.name), (data.args as Record<string, unknown>) ?? {}))
      .finally(() => aiCommands--)
      .then((result) => answer(sessionId, id, { ok: true, result: result ?? null }))
      .catch((e: unknown) =>
        answer(sessionId, id, { ok: false, error: e instanceof Error ? e.message : String(e) })
      );
  }
}

/** Reads the event stream; reconnects after a drop until switched off. */
async function listen(sessionId: string, signal: AbortSignal) {
  let wait = 1000;
  let refused = false;
  while (!signal.aborted) {
    try {
      const res = await fetch(`${API_BASE}/api/live/sessions/${sessionId}/events`, {
        // After a refusal (token ran out), a fresh API page token.
        headers: { ...(await authHeaders(refused)), [PAGE_TOKEN_HEADER]: pageToken ?? '' },
        signal,
      });
      // 403 is the API key's refusal, or the session's when this tab's token is not its own.
      const detail = res.status === 403 ? await res.text() : '';
      refused = res.status === 401 || (res.status === 403 && !detail.includes(NOT_OURS));
      if (res.status === 404 || detail.includes(NOT_OURS))
        throw new Ended('The live session has ended.');
      if (!res.ok || !res.body) throw new Error(`Live connection failed (${res.status}).`);
      wait = 1000;
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        let cut: number;
        while ((cut = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, cut);
          buffer = buffer.slice(cut + 2);
          const type = /^event: (.*)$/m.exec(block)?.[1];
          const data = /^data: (.*)$/m.exec(block)?.[1];
          if (type && data) handleEvent(sessionId, type, JSON.parse(data));
        }
      }
    } catch (e) {
      if (signal.aborted) return;
      if (e instanceof Ended) {
        // Not this tab's any more: forget it, so a reload starts afresh.
        forgetSaved();
        pageToken = null;
        set({ status: 'error', error: e.message, paused: false });
        return;
      }
    }
    if (signal.aborted) return;
    set({ status: 'connecting' });
    await new Promise((r) => setTimeout(r, wait));
    wait = Math.min(wait * 2, 15_000);
  }
}

export async function connectLive() {
  if (useLiveStore.getState().status !== 'off' && useLiveStore.getState().status !== 'error')
    return;
  set({ status: 'connecting', error: null });
  try {
    const { session_id, project_id, page_token, paused } = await openSession();
    pageToken = page_token;
    try {
      sessionStorage.setItem(SAVED, JSON.stringify({ session_id, page_token }));
    } catch {
      // Storage blocked: a reload then starts a new session.
    }
    set({ sessionId: session_id, projectId: project_id, paused: Boolean(paused), log: [] });
    abort = new AbortController();
    void listen(session_id, abort.signal);
  } catch (e) {
    set({ status: 'error', error: e instanceof Error ? e.message : String(e) });
  }
}

export async function disconnectLive() {
  const { sessionId } = useLiveStore.getState();
  const headers = own();
  abort?.abort();
  abort = null;
  forgetSaved();
  set({ status: 'off', sessionId: null, projectId: null, error: null, paused: false, log: [] });
  if (sessionId) await client.delete(`/api/live/sessions/${sessionId}`, headers).catch(() => {});
  pageToken = null;
}

/** Pause or resume the AI on this page; the server refuses it while paused. */
export async function setAiPaused(paused: boolean) {
  const { sessionId } = useLiveStore.getState();
  if (!sessionId) return;
  const { data } = await client.put(`/api/live/sessions/${sessionId}/pause`, { paused }, own());
  set({ paused: Boolean(data.paused) });
}

/** After a reload, reconnect a tab that was connected. */
export function resumeLive() {
  if (loadSaved()) void connectLive();
}
