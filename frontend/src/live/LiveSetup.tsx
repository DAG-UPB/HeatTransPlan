/** How to give an AI agent access: add this app's MCP address to the agent,
 *  then connect the page. Nothing to install: the backend serves MCP at /mcp.
 *  Where the server checks keys, the visitor first gets one with one click
 *  (POST /api/keys); the server keeps nothing, this browser keeps a copy. */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Copy, X } from 'lucide-react';
import client from '../api/client';
import { useFeatures } from '../hooks/useFeatures';
import '../components/analysis/CopFormulaModal.css';

/** A text to copy; wrap: a sentence (not a command), broken into lines. */
function Command({ text, wrap = false }: { text: string; wrap?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className={`live-setup-cmd${wrap ? ' live-setup-cmd-wrap' : ''}`}>
      <pre className="notranslate">{text}</pre>
      <button
        type="button"
        className="live-icon"
        onClick={() => navigator.clipboard?.writeText(text)}
        title={t('live.copy_command')}
        aria-label={t('live.copy_command')}
      >
        <Copy size={13} />
      </button>
    </div>
  );
}

// In this browser only, so the dialog shows the key again on this device.
const KEY_STORE = 'heattransplan.apiKey';

function storedKey(): string {
  try {
    return localStorage.getItem(KEY_STORE) || '';
  } catch {
    return '';
  }
}

/** Get a key (once; it cannot be shown again by the server) or show the one this browser kept. */
function ApiKey({ apiKey, onKey }: { apiKey: string; onKey: (key: string) => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const get = async () => {
    setBusy(true);
    setError('');
    try {
      const { data } = await client.post<{ key: string }>('/api/keys');
      try {
        localStorage.setItem(KEY_STORE, data.key);
      } catch {
        /* blocked storage: shown this time only */
      }
      onKey(data.key);
    } catch (e) {
      setError(
        t(
          axios.isAxiosError(e) && e.response?.status === 429
            ? 'live.key_too_many'
            : 'live.key_failed'
        )
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="live-setup-key">
      <div>
        <strong>{t('live.key_title')}</strong> {!apiKey && t('live.key_why')}
      </div>
      {apiKey ? (
        <>
          <Command text={apiKey} />
          <div className="cf-muted">{t('live.key_keep')}</div>
        </>
      ) : (
        <button type="button" className="cf-btn cf-btn-primary" onClick={get} disabled={busy}>
          {t('live.key_get')}
        </button>
      )}
      {error && (
        <div className="cf-muted" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

export default function LiveSetup({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const features = useFeatures();
  const [apiKey, setApiKey] = useState(storedKey);
  // Caddy (and Vite in development) route /mcp to the backend.
  const url = `${window.location.origin}/mcp`;
  const needKey = features.user_keys;
  // Connectors (Claude.ai, ChatGPT, Le Chat) cannot send headers: the key goes in the address.
  const keyedUrl = needKey && apiKey ? `${url}?key=${encodeURIComponent(apiKey)}` : url;
  const header = needKey && apiKey ? `Authorization: Bearer ${apiKey}` : '';
  // Agents that run in the cloud (web chats, connectors) need a public https
  // address; an app served over http is reachable from this computer only.
  const online = window.location.protocol === 'https:';

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Portal: the header's stacking context would put the dialog under the map controls.
  return createPortal(
    <div className="cf-backdrop" role="presentation" onClick={onClose}>
      <div
        className="cf-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={t('live.setup_title')}
      >
        <header className="cf-header">
          <h3>{t('live.setup_title')}</h3>
          <button className="cf-close" onClick={onClose} aria-label={t('live.close')}>
            <X size={16} />
          </button>
        </header>
        <div className="cf-body live-setup">
          <p>{t('live.setup_intro')}</p>
          <ol>
            {needKey && (
              <li>
                <ApiKey apiKey={apiKey} onKey={setApiKey} />
              </li>
            )}
            {(!needKey || apiKey) && (
              <li>
                {t('live.setup_add')}
                <Command text={keyedUrl} />
                {needKey && <div className="cf-muted">{t('live.key_in_url')}</div>}
                <div className="cf-muted">{t('live.setup_where')}</div>
                {!online && <div className="cf-muted">{t('live.setup_local')}</div>}
                <div className="cf-muted">{t('live.setup_self')}</div>
                <Command text={t('live.setup_self_text', { url: keyedUrl })} wrap />
                <div className="cf-muted">{t('live.setup_permissions')}</div>
                {features.api_key && !needKey && (
                  <div className="cf-muted">{t('live.setup_key')}</div>
                )}
                {/* Well-known agents as examples; the steps above work for any. */}
                <details className="live-setup-examples">
                  <summary>{t('live.setup_examples')}</summary>
                  <div className="cf-muted">{t('live.setup_ex_where')}</div>
                  <ul className="live-setup-ex">
                    <li>{t('live.setup_ex_claude')}</li>
                    <li>{t('live.setup_ex_chatgpt')}</li>
                    <li>{t('live.setup_ex_mistral')}</li>
                    <li>
                      {t('live.setup_ex_claude_code')}
                      <Command
                        text={`claude mcp add --transport http heattransplan ${url}${header ? ` --header "${header}"` : ''}`}
                      />
                    </li>
                    <li>
                      {t('live.setup_ex_gemini')}
                      <Command
                        text={`gemini mcp add --transport http heattransplan ${url}${header ? ` --header "${header}"` : ''}`}
                      />
                      <Command
                        text={JSON.stringify(
                          {
                            mcpServers: {
                              heattransplan: {
                                httpUrl: url,
                                ...(header
                                  ? { headers: { Authorization: `Bearer ${apiKey}` } }
                                  : {}),
                              },
                            },
                          },
                          null,
                          2
                        )}
                      />
                    </li>
                    {header && (
                      <li>
                        {t('live.setup_ex_cursor')}
                        <Command
                          text={JSON.stringify(
                            {
                              mcpServers: {
                                heattransplan: {
                                  url,
                                  headers: { Authorization: `Bearer ${apiKey}` },
                                },
                              },
                            },
                            null,
                            2
                          )}
                        />
                      </li>
                    )}
                  </ul>
                  <div className="cf-muted">{t('live.setup_ex_note')}</div>
                </details>
              </li>
            )}
            <li>{t('live.setup_connect')}</li>
          </ol>
          <p>{t('live.setup_guided')}</p>
          <p className="cf-muted">{t('live.setup_files')}</p>
          <p>
            <a
              href="/docs/api_and_mcp.html#the-mcp-server"
              target="_blank"
              rel="noopener noreferrer"
            >
              {t('live.setup_docs')} ↗
            </a>
          </p>
          <p>
            <a href="/docs/ai_briefing.html" target="_blank" rel="noopener noreferrer">
              {t('live.setup_briefing')} ↗
            </a>
          </p>
        </div>
      </div>
    </div>,
    document.body
  );
}
