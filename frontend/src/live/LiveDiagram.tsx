/** How Connect AI works, as one picture: you on the page, the AI assistant,
 *  and the HeatTransPlan server between them. Drawn here (not an image) so it
 *  follows the theme and the language. Shown at the top of the setup dialog. */

import { Bot } from 'lucide-react';
import { useTranslation } from 'react-i18next';

// Three boxes side by side in a 1000 × 330 drawing.
const BOX = { y: 72, w: 260, h: 214 };
const XS = [10, 370, 730];

export default function LiveDiagram() {
  const { t } = useTranslation();
  const boxes = [
    { key: 'you', className: 'ld-you' },
    { key: 'ai', className: 'ld-ai' },
    { key: 'app', className: 'ld-app' },
  ] as const;
  const mid = (i: number) => XS[i] + BOX.w / 2;
  // An arrow pair in the gap between box i and box i + 1: the request goes
  // right above, the answer comes back left below.
  const gap = (i: number, there: string, back: string) => {
    const x1 = XS[i] + BOX.w + 8;
    const x2 = XS[i + 1] - 8;
    const cx = (x1 + x2) / 2;
    const y = BOX.y + BOX.h / 2;
    return (
      <g key={i}>
        <text x={cx} y={y - 22} textAnchor="middle" className="ld-arrow-label">
          {there}
        </text>
        <line
          x1={x1}
          y1={y - 8}
          x2={x2}
          y2={y - 8}
          className="ld-arrow"
          markerEnd="url(#ld-head)"
        />
        <line
          x1={x2}
          y1={y + 8}
          x2={x1}
          y2={y + 8}
          className="ld-arrow"
          markerEnd="url(#ld-head)"
        />
        <text x={cx} y={y + 34} textAnchor="middle" className="ld-arrow-label">
          {back}
        </text>
      </g>
    );
  };

  return (
    <div className="ld-wrap">
      <svg className="ld" viewBox="0 0 1000 330" role="img" aria-label={t('live.diagram.label')}>
        <defs>
          <marker
            id="ld-head"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="9"
            markerHeight="9"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" className="ld-head" />
          </marker>
        </defs>

        {/* The page and the server talk directly: commands go to the page,
            the page shows every step live. */}
        <path
          d={`M${mid(2)} ${BOX.y - 6} C ${mid(2) - 60} 34, ${mid(0) + 60} 34, ${mid(0)} ${BOX.y - 6}`}
          className="ld-arrow ld-dashed"
          markerStart="url(#ld-head)"
          markerEnd="url(#ld-head)"
        />
        <text x={500} y={18} textAnchor="middle" className="ld-arrow-label ld-top-label">
          {t('live.diagram.live')}
        </text>

        {boxes.map(({ key, className }, i) => (
          <g key={key} className={className}>
            <rect x={XS[i]} y={BOX.y} width={BOX.w} height={BOX.h} rx={16} className="ld-box" />
            {key === 'ai' && (
              <Bot x={XS[i] + 22} y={BOX.y + 22} width={26} height={26} className="ld-icon" />
            )}
            <text
              x={mid(i) + (key === 'ai' ? 14 : 0)}
              y={BOX.y + 44}
              textAnchor="middle"
              className="ld-title"
            >
              {t(`live.diagram.${key}.title`)}
            </text>
            <text x={mid(i)} y={BOX.y + 68} textAnchor="middle" className="ld-sub">
              {t(`live.diagram.${key}.sub`)}
            </text>
            {[1, 2, 3].map((n) => (
              <g key={n}>
                <circle cx={XS[i] + 24} cy={BOX.y + 70 + n * 36} r={4} className="ld-dot" />
                <text x={XS[i] + 38} y={BOX.y + 75 + n * 36} className="ld-point">
                  {t(`live.diagram.${key}.p${n}`)}
                </text>
              </g>
            ))}
          </g>
        ))}

        {gap(0, t('live.diagram.ask'), t('live.diagram.answer'))}
        {gap(1, t('live.diagram.tools'), t('live.diagram.results'))}

        <text x={500} y={318} textAnchor="middle" className="ld-note">
          {t('live.diagram.note')}
        </text>
      </svg>
    </div>
  );
}
