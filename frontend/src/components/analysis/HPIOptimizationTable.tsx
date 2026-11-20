/** The optimization panel's table: one row per refrigerant type plus the
 *  archetypes, sortable by every column. */

import type { CSSProperties, ReactNode } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import type { OptimizedIntegrationPoint } from '../../types/analysis';
import ChartHelpButton from '../ui/ChartHelpButton';
import { formulaHtml } from '../../utils/formulaHtml';
import { refBaseName, type SortConfig, type SortKey } from './hpiOptimizationRows';

interface Props {
  rows: OptimizedIntegrationPoint[];
  selectedPoints: OptimizedIntegrationPoint[];
  sortConfigs: SortConfig[];
  onSort: (key: SortKey) => void;
  tMin: number;
  isDark: boolean;
  feasibleCount: number;
  diagnosticMessages: string[];
}

/** A symbol label in scientific notation: "Q_sink (kW)" → Q<sub>sink</sub> (kW),
 *  kept out of the header row's capitals. Anything else is returned as it is. */
const symbol = (label: string) => {
  const m = label.match(/^(\w)_(\S+)(.*)$/);
  return m ? (
    <span style={{ textTransform: 'none' }}>
      {m[1]}
      <sub>{m[2]}</sub>
      {m[3]}
    </span>
  ) : (
    label
  );
};

// The header sticks as a whole (thead): its two rows then stay stacked.
const thStyle = {
  cursor: 'pointer',
  userSelect: 'none' as const,
  // Headers carry a label plus a help bulb plus a sort arrow; letting them
  // wrap is what made rows two lines tall.
  whiteSpace: 'nowrap' as const,
};

// The type cell holds a badge and a technology name side by side, so it needs
// more room than the numeric columns or its content wraps onto a second line.
const typeThStyle = { ...thStyle, minWidth: '190px' };
// Holds only "Natural"/"Synthetic", so it needs far less room than its
// header once implied.
const narrowThStyle = { ...thStyle, width: '1%' };

function SortIcon({ sortConfigs, sortKey }: { sortConfigs: SortConfig[]; sortKey: SortKey }) {
  const idx = sortConfigs.findIndex((c) => c.key === sortKey);
  if (idx === -1) return null;
  const arrow = sortConfigs[idx].direction === 'asc' ? '↑' : '↓';
  return (
    <span
      style={{
        marginLeft: '4px',
        fontSize: idx === 0 ? '1em' : '0.8em',
        opacity: idx === 0 ? 1 : 0.6,
      }}
    >
      {arrow}
      {idx > 0 && <span style={{ fontSize: '0.7em' }}>({idx + 1})</span>}
    </span>
  );
}

/** A clickable column header with its help bulb and, optionally, the arrow
 *  showing where it sits in the sort order. */
function SortableHeader({
  label,
  helpTitle,
  helpText,
  sortKey,
  onSort,
  icon,
  style = thStyle,
}: {
  label: ReactNode;
  helpTitle: string;
  helpText: string;
  sortKey: SortKey;
  onSort: (key: SortKey) => void;
  icon: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <th style={style} onClick={() => onSort(sortKey)}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
        {label}
        <span onClick={(e) => e.stopPropagation()}>
          <ChartHelpButton title={helpTitle} description={helpText} inline={true} />
        </span>
        {icon}
      </div>
    </th>
  );
}

export default function HPIOptimizationTable({
  rows,
  selectedPoints,
  sortConfigs,
  onSort,
  tMin,
  isDark,
  feasibleCount,
  diagnosticMessages,
}: Props) {
  const { t, i18n } = useTranslation();

  // Each section's tint, matching the heat pump overlay in the chart (the
  // pump's lilac, the sink's blue, the source's red). Only the header carries
  // it; the values below stay plain, and a line marks where a section starts.
  const sinkCell = { backgroundColor: isDark ? 'rgba(59,130,246,0.14)' : 'rgba(143,174,224,0.20)' };
  const sourceCell = {
    backgroundColor: isDark ? 'rgba(248,113,113,0.14)' : 'rgba(232,139,139,0.20)',
  };
  const copCell = {
    backgroundColor: isDark ? 'rgba(167,139,250,0.16)' : 'rgba(124,58,237,0.13)',
  };
  // Where one section ends and the next starts (pump | sink | source): a line
  // clearly darker than the grid, in header and rows alike.
  const divider: CSSProperties = {
    borderLeft: '2px solid color-mix(in srgb, var(--text-main) 40%, transparent)',
  };
  const startsSection = (key: SortKey) => key === 'medium_sink' || key === 'Q_source';

  // Carnot is not a fitted correlation like the other archetypes — it is the
  // thermodynamic relation between the two temperatures — so it gets its own
  // explanation rather than the "published regressions" one.
  const oneDecimal = (v: number) =>
    v.toLocaleString(i18n.language, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  const entryHint = (pt: OptimizedIntegrationPoint) =>
    !pt.theoretical
      ? t('optimization.real_hint')
      : pt.refrigerant === 'Carnot'
        ? t('optimization.carnot_hint')
        : t('optimization.theoretical_hint');

  const icon = (key: SortKey) => <SortIcon sortConfigs={sortConfigs} sortKey={key} />;
  // A header cell in its group's colour: the pale tint laid over a solid
  // surface, as the header stays put while the rows scroll beneath it.
  const solid = (colour: string): CSSProperties => ({
    background: `linear-gradient(${colour}, ${colour}), var(--surface)`,
  });
  // Each column header takes its group's colour, as the group row above it:
  // the heat pump's lilac, the sink's blue, the source's red.
  const groupColour = (key: SortKey) =>
    (['medium_sink', 'Q_demand', 'T_sink'] as SortKey[]).includes(key)
      ? sinkCell.backgroundColor
      : (['Q_source', 'T_source'] as SortKey[]).includes(key)
        ? sourceCell.backgroundColor
        : copCell.backgroundColor;
  const header = (
    key: SortKey,
    label: ReactNode,
    helpTitle: string,
    helpText: string,
    opts: { style?: CSSProperties; noIcon?: boolean } = {}
  ) => (
    <SortableHeader
      label={label}
      helpTitle={helpTitle}
      helpText={helpText}
      sortKey={key}
      onSort={onSort}
      icon={opts.noIcon ? null : icon(key)}
      style={{
        ...(opts.style ?? thStyle),
        ...solid(groupColour(key)),
        ...(startsSection(key) ? divider : {}),
      }}
    />
  );

  return (
    <div className="pa-hp-table-wrap" style={{ maxHeight: '440px', overflowY: 'auto' }}>
      {rows.length > 0 ? (
        <>
          <table className="pa-table pa-hp-table">
            <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
              {/* Two rows: what a column belongs to (the heat pump, its sink,
                  its source), then what it is. Short labels; the help bulb
                  of each column keeps the full name and explanation. */}
              <tr className="pa-hp-groups">
                {/* The heat pump's own lilac, as its COP column and its box. */}
                <th colSpan={6} style={solid(copCell.backgroundColor)}>
                  {t('optimization.panel.groups.heat_pump')}
                </th>
                <th colSpan={4} style={{ ...solid(sinkCell.backgroundColor), ...divider }}>
                  {t('optimization.panel.groups.sink')}
                </th>
                <th colSpan={3} style={{ ...solid(sourceCell.backgroundColor), ...divider }}>
                  {t('optimization.panel.groups.source')}
                </th>
              </tr>
              <tr>
                {header(
                  'theoretical',
                  t('optimization.panel.headers.entry_type'),
                  t('optimization.panel.headers.entry_type'),
                  t('optimization.entry_type_hint'),
                  { style: typeThStyle }
                )}
                {header(
                  'refrigerant',
                  t('optimization.panel.headers.refrigerant'),
                  t('optimization.title_refrigerant'),
                  t('optimization.tooltip_refrigerant')
                )}
                {header(
                  'hp_level',
                  t('optimization.panel.sub.compressors'),
                  t('optimization.title_hp_stages'),
                  t('optimization.tooltip_hp_stages')
                )}
                {header(
                  'refrigerant_type',
                  t('optimization.panel.sub.refrigerant_type'),
                  t('optimization.title_refrigerant_type'),
                  t('optimization.tooltip_refrigerant_type'),
                  { style: narrowThStyle }
                )}
                {header(
                  'COP',
                  <span className="notranslate">{t('optimization.panel.headers.cop')}</span>,
                  t('optimization.title_cop'),
                  t('optimization.tooltip_cop')
                )}
                {header(
                  'W_el',
                  symbol(t('optimization.panel.headers.w_el')),
                  t('optimization.title_w_el'),
                  t('optimization.tooltip_w_el')
                )}
                {header(
                  'medium_sink',
                  t('optimization.panel.sub.medium'),
                  t('optimization.title_medium_sink'),
                  t('optimization.desc_medium_sink')
                )}
                {header(
                  'Q_demand',
                  <span style={{ textTransform: 'none' }}>{t('optimization.panel.sub.q')}</span>,
                  t('optimization.title_q_sink'),
                  t('optimization.tooltip_q_sink')
                )}
                {header(
                  'T_sink',
                  t('optimization.panel.sub.temp'),
                  t('optimization.title_actual_sink_temp'),
                  t('optimization.desc_actual_sink_temp')
                )}
                {header(
                  'T_sink',
                  t('optimization.panel.sub.temp_shifted', { k: `+${tMin / 2}` }),
                  t('optimization.title_shifted_sink_temp'),
                  t('optimization.desc_shifted_sink_temp'),
                  { noIcon: true }
                )}
                {header(
                  'Q_source',
                  <span style={{ textTransform: 'none' }}>{t('optimization.panel.sub.q')}</span>,
                  t('optimization.title_q_source'),
                  t('optimization.tooltip_q_source')
                )}
                {header(
                  'T_source',
                  t('optimization.panel.sub.temp'),
                  t('optimization.title_actual_source_temp'),
                  t('optimization.desc_actual_source_temp')
                )}
                {header(
                  'T_source',
                  t('optimization.panel.sub.temp_shifted', { k: `−${tMin / 2}` }),
                  t('optimization.title_shifted_source_temp'),
                  t('optimization.desc_shifted_source_temp'),
                  { noIcon: true }
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((pt, i) => {
                const isSelected = selectedPoints.some(
                  (sp) => sp.refrigerant === pt.refrigerant && sp.T_sink === pt.T_sink
                );
                const refName = refBaseName(pt.refrigerant);
                return (
                  <tr
                    key={i}
                    style={isSelected ? { backgroundColor: isDark ? '#334155' : '#E2E8F0' } : {}}
                  >
                    <td>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '0.1rem 0.4rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            backgroundColor: pt.theoretical
                              ? isDark
                                ? '#065F46'
                                : '#D1FAE5'
                              : isDark
                                ? '#1E3A8A'
                                : '#DBEAFE',
                            color: pt.theoretical
                              ? isDark
                                ? '#A7F3D0'
                                : '#065F46'
                              : isDark
                                ? '#BFDBFE'
                                : '#1E3A8A',
                          }}
                          title={entryHint(pt)}
                        >
                          {pt.theoretical ? t('optimization.theoretical') : t('optimization.real')}
                        </span>
                        {/* The refrigerant column is blank for archetypes,
                          so the technology name rides here — otherwise
                          Carnot and VHTHP rows look identical. Kept on
                          the same line so every row is one line tall. */}
                        <span
                          style={{
                            fontSize: '0.75rem',
                            color: isDark ? '#94A3B8' : '#64748B',
                          }}
                        >
                          {/* The Carnot entry is 50 % of the ceiling, not
                            the ceiling, so it says so on the row. */}
                          {pt.theoretical
                            ? pt.refrigerant === 'Carnot'
                              ? t('optimization.carnot_50')
                              : pt.refrigerant
                            : ''}
                        </span>
                        {pt.calculation_details && (
                          <ChartHelpButton
                            inline
                            title={
                              pt.theoretical
                                ? `${pt.refrigerant} — ${t('optimization.calculation')}`
                                : t('optimization.calculation')
                            }
                            description={
                              <>
                                <p>{entryHint(pt)}</p>
                                {pt.theoretical ? (
                                  // An archetype's formula, with its temperatures filled in.
                                  <pre
                                    style={{
                                      margin: 0,
                                      whiteSpace: 'pre-wrap',
                                      fontFamily: 'monospace',
                                      fontSize: '0.9em',
                                    }}
                                    dangerouslySetInnerHTML={{
                                      // The server's Carnot text opens with an English
                                      // sentence that repeats the hint above: start at the formula.
                                      __html: formulaHtml(
                                        pt.calculation_details.slice(
                                          Math.max(0, pt.calculation_details.indexOf('COP ='))
                                        )
                                      ),
                                    }}
                                  />
                                ) : (
                                  // A model row has no formula, only its operating
                                  // point: written here in the page's language.
                                  <p>
                                    <Trans
                                      i18nKey="optimization.real_point"
                                      values={{
                                        name: pt.refrigerant,
                                        medium: t(
                                          `optimization.medium.${pt.medium_sink}`,
                                          pt.medium_sink
                                        ),
                                        stages: pt.hp_level,
                                        source: oneDecimal(pt.T_source),
                                        sink: oneDecimal(pt.T_sink),
                                      }}
                                      components={{ sub: <sub /> }}
                                    />
                                  </p>
                                )}
                              </>
                            }
                          />
                        )}
                      </div>
                    </td>
                    {/* In the header's group order: heat pump, sink, source.
                        Refrigerant, stage count, type and medium describe a
                        trained machine; an archetype has none of them. */}
                    <td>{pt.theoretical ? '' : refName}</td>
                    <td>{pt.theoretical ? '' : pt.hp_level}</td>
                    <td>
                      {pt.theoretical
                        ? ''
                        : t(`optimization.refrigerant_types.${pt.refrigerant_type}`, {
                            defaultValue: pt.refrigerant_type,
                          })}
                    </td>
                    <td style={{ fontWeight: 600 }}>{pt.COP.toFixed(2)}</td>
                    <td>{(pt.Q_demand / pt.COP).toFixed(1)}</td>
                    <td style={divider}>{pt.theoretical ? '' : pt.medium_sink}</td>
                    <td
                      title={
                        pt.source_limited && pt.Q_demand_total
                          ? t('ui.source_limited', {
                              pct: ((100 * pt.Q_demand) / pt.Q_demand_total).toFixed(0),
                              kw: pt.Q_demand_total.toFixed(1),
                            })
                          : undefined
                      }
                    >
                      {pt.Q_demand.toFixed(1)}
                      {pt.source_limited && pt.Q_demand_total ? (
                        <span
                          style={{
                            color: isDark ? '#FBBF24' : '#B45309',
                            marginLeft: '0.25rem',
                          }}
                        >
                          * / {pt.Q_demand_total.toFixed(1)}
                        </span>
                      ) : null}
                    </td>
                    <td>{(pt.T_sink - tMin / 2).toFixed(1)}</td>
                    <td>{pt.T_sink.toFixed(1)}</td>
                    <td style={divider}>{((pt.Q_demand * (pt.COP - 1)) / pt.COP).toFixed(1)}</td>
                    <td>{(pt.T_source + tMin / 2).toFixed(1)}</td>
                    <td>{pt.T_source.toFixed(1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      ) : (
        <div style={{ marginTop: '1rem', color: isDark ? '#94A3B8' : '#64748B' }}>
          <p>{feasibleCount === 0 ? t('ui.no_hp_possible') : t('ui.no_hp_filters')}</p>
          {feasibleCount === 0 &&
            diagnosticMessages.map((m, i) => (
              <p key={i} style={{ marginTop: '0.5rem' }}>
                {m}
              </p>
            ))}
        </div>
      )}
      {rows.some((p) => p.source_limited) && (
        <p
          style={{
            marginTop: '0.75rem',
            fontSize: '0.85rem',
            color: isDark ? '#FBBF24' : '#B45309',
          }}
        >
          * Source-limited: the available waste heat covers only part of the demand above T_sink.
          The second figure is the full requirement; the rest still has to come from a utility.
        </p>
      )}
      <p
        style={{
          marginTop: '1rem',
          fontSize: '0.85rem',
          color: isDark ? '#94A3B8' : '#64748B',
        }}
      >
        {t('optimization.panel.instruction')}
      </p>
    </div>
  );
}
