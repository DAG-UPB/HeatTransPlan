/** The header control for the AI link: connect, show the session code the AI
 *  needs, disconnect. Also bridges the router, so the AI can navigate and the
 *  view knows the page. */

import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Bot, CircleHelp, Copy, LoaderCircle, X } from 'lucide-react';
import { CommandError, useLiveCommand } from './commands';
import { setCurrentPage } from './view';
import LiveSetup from './LiveSetup';
import AiControls from './AiControls';
import { connectLive, disconnectLive, resumeLive, useLiveStore } from './liveClient';

const PAGES: Record<string, string> = {
  home: '/',
  'data-collection': '/data-collection',
  'potential-analysis': '/potential-analysis',
};

export default function LiveButton() {
  const { t } = useTranslation();
  const status = useLiveStore((s) => s.status);
  const sessionId = useLiveStore((s) => s.sessionId);
  const error = useLiveStore((s) => s.error);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [setupOpen, setSetupOpen] = useState(false);

  useEffect(() => {
    setCurrentPage(pathname);
  }, [pathname]);

  useEffect(() => resumeLive(), []);

  useLiveCommand('navigate', (args) => {
    const path = PAGES[String(args.page)];
    if (!path) throw new CommandError(`page must be one of ${Object.keys(PAGES).join(', ')}`);
    navigate(path);
    return { page: path };
  });

  // How to set the assistant up: part of the AI control, connected or not.
  const helpButton = (className: string) => (
    <button
      type="button"
      className={className}
      onClick={() => setSetupOpen(true)}
      data-tip={t('live.setup_title')}
      aria-label={t('live.setup_title')}
    >
      <CircleHelp size={className === 'live-icon' ? 13 : 14} />
    </button>
  );
  const setup = setupOpen && <LiveSetup onClose={() => setSetupOpen(false)} />;

  if (status === 'on' || status === 'connecting') {
    return (
      <>
        <span className="live-badge">
          {status === 'connecting' ? (
            <LoaderCircle size={14} className="pa-spin" />
          ) : (
            <span className="live-dot" />
          )}
          <Bot size={14} />
          <code className="notranslate" data-tip={t('live.code')}>
            {sessionId ?? '…'}
          </code>
          {sessionId && (
            <button
              type="button"
              className="live-icon"
              onClick={() => navigator.clipboard?.writeText(sessionId)}
              data-tip={t('live.copy')}
              aria-label={t('live.copy')}
            >
              <Copy size={13} />
            </button>
          )}
          {status === 'on' && <AiControls />}
          {helpButton('live-icon')}
          <button
            type="button"
            className="live-icon"
            onClick={() => void disconnectLive()}
            data-tip={t('live.disconnect')}
            aria-label={t('live.disconnect')}
          >
            <X size={13} />
          </button>
        </span>
        {setup}
      </>
    );
  }

  return (
    <>
      <span className="live-group">
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => void connectLive()}
          title={status === 'error' ? t('live.error', { msg: error }) : t('live.connect_hint')}
          aria-label={t('live.connect')}
        >
          <Bot size={14} /> <span className="nav-btn-label">{t('live.connect')}</span>
        </button>
        {helpButton('btn btn-sm live-group-help')}
      </span>
      {setup}
    </>
  );
}
