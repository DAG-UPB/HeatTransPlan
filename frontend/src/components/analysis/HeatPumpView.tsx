/** The COP model in two tabs. "Heat pump": the pump drawn as its three
 *  circuits, with the two temperatures the 2-temperature COP model reads
 *  (source out, sink out) as fields to try out; the COP answers live, and
 *  inputs the training data never had are named. "COP model": the model as one
 *  circle, its input variables going in and the COP coming out. */

import { X } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { rateCopPoint } from '../../api/analysis';
import type {
  CopPointResult,
  OptimizedIntegrationPoint,
  Profile,
  SearchTemp,
} from '../../types/analysis';
import SearchSize from './SearchSize';
import './CopFormulaModal.css';
import './HeatPumpView.css';

type Temp = 'sourceIn' | 'sourceOut' | 'sinkIn' | 'sinkOut';
type Side = 'source' | 'sink';
const SIDE: Record<Temp, Side> = {
  sourceIn: 'source',
  sourceOut: 'source',
  sinkIn: 'sink',
  sinkOut: 'sink',
};
// The names the optimization request uses (search_temps).
const API: Record<Temp, SearchTemp> = {
  sourceIn: 'source_in',
  sourceOut: 'source_out',
  sinkIn: 'sink_in',
  sinkOut: 'sink_out',
};
const TEMPS: Temp[] = ['sourceIn', 'sourceOut', 'sinkIn', 'sinkOut'];
// The trained models' own column names for the temperatures.
const GERMAN_COLUMN: Record<Temp, string> = {
  sourceIn: 'T_Vorlauf_Quelle',
  sourceOut: 'T_Rücklauf_Quelle',
  sinkIn: 'T_Rücklauf_Senke',
  sinkOut: 'T_Vorlauf_Senke',
};
const GERMAN: Record<Temp, string> = {
  sourceIn: 'T_vorlauf_Quelle',
  sourceOut: 'T_rücklauf_Quelle',
  sinkIn: 'T_rücklauf_Senke',
  sinkOut: 'T_Vorlauf_Senke',
};

export interface PumpOption {
  refrigerant: string;
  medium_sink: string;
}

interface Props {
  point: OptimizedIntegrationPoint;
  pinchTemperature: number;
  tMin: number;
  pumps: PumpOption[];
  /** The profiles the optimization searched along (shifted scale, ascending T). */
  sourceProfile: Profile;
  sinkProfile: Profile;
  /** Which temperatures the optimization searches; the rest sit at the pinch. */
  searchTemps: SearchTemp[];
  /** Changes the optimization's search (it re-runs). */
  onSearchTemps: (next: SearchTemp[]) => void;
  onClose: () => void;
}

const SOURCE = '#0A75C4';
const SINK = '#C138A0';
const FLUID = '#7E3FA8';

// The slider from the heat pump to its COP model: 0 shows the pump, 1 the
// model. Between, each input travels from where it sits in the pump to its
// circle in front of the model, the pump fades out and the model fades in.
const smooth = (from: number, to: number, x: number) => {
  const k = Math.min(1, Math.max(0, (x - from) / (to - from)));
  return k * k * (3 - 2 * k);
};
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
// The model's inputs as circles (radius INPUT_R) in a column, the model a
// rectangle, the COP a circle on the right; all in the 1000 × 450 drawing.
const INPUT_X = 250;
const INPUT_R = 38;
const MODEL = { x: 440, y: 160, w: 200, h: 170 };
const OUTPUT = { x: 850, y: 245, r: 52 };

export default function HeatPumpView({
  point,
  pinchTemperature,
  tMin,
  pumps,
  sourceProfile,
  sinkProfile,
  searchTemps,
  onSearchTemps,
  onClose,
}: Props) {
  const { t } = useTranslation();
  const half = tMin / 2;
  // Where the search stands on each profile (shifted scale): a searched
  // temperature follows its side, a fixed one keeps its own value, which starts
  // at the pinch.
  const startGrid = { source: point.T_source, sink: point.T_sink };
  const startFixed: Record<Temp, number> = {
    sourceIn: pinchTemperature,
    sourceOut: pinchTemperature,
    sinkIn: pinchTemperature,
    sinkOut: pinchTemperature,
  };
  const [grid, setGrid] = useState<Record<Side, number>>(startGrid);
  const [fixed, setFixed] = useState(startFixed);
  // The text of the field being typed in, so "6" on the way to "66" stays put.
  const [editing, setEditing] = useState<{ k: Temp; raw: string } | null>(null);
  // 0 = the heat pump, 1 = the COP model (see smooth/lerp above).
  const [morph, setMorph] = useState(0);
  const glideFrame = useRef(0);
  // Clicking an end of the slider glides there instead of jumping.
  const glide = (to: number) => {
    cancelAnimationFrame(glideFrame.current);
    const from = morph;
    const start = performance.now();
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / 700);
      setMorph(lerp(from, to, smooth(0, 1, k)));
      if (k < 1) glideFrame.current = requestAnimationFrame(step);
    };
    glideFrame.current = requestAnimationFrame(step);
  };
  useEffect(() => () => cancelAnimationFrame(glideFrame.current), []);
  const searched = (k: Temp) => searchTemps.includes(API[k]);
  const value = (k: Temp) => (searched(k) ? grid[SIDE[k]] : fixed[k]);
  const temps: Record<Temp, number> = {
    sourceIn: value('sourceIn'),
    sourceOut: value('sourceOut'),
    sinkIn: value('sinkIn'),
    sinkOut: value('sinkOut'),
  };

  // The pump shown: the selected one when it is a real machine (the trained
  // models need one), otherwise the first real one in the results.
  const startPump = point.theoretical
    ? pumps[0]
    : (pumps.find(
        (p) => p.refrigerant === point.refrigerant && p.medium_sink === point.medium_sink
      ) ?? pumps[0]);
  const [pump, setPump] = useState<PumpOption | undefined>(startPump);
  const [result, setResult] = useState<CopPointResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { sourceIn, sourceOut, sinkIn, sinkOut } = temps;
  useEffect(() => {
    if (!pump) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      rateCopPoint({
        refrigerant: pump.refrigerant,
        medium_sink: pump.medium_sink,
        T_source_in: sourceIn,
        T_source_out: sourceOut,
        T_sink_in: sinkIn,
        T_sink_out: sinkOut,
        delta_t_min: tMin,
        // The backend reads demand and waste heat off the profiles and
        // balances them at its COP, as the optimization does.
        source_profile: sourceProfile,
        sink_profile: sinkProfile,
        T_source_profile: grid.source,
        T_sink_profile: grid.sink,
        q_sink_default: point.Q_demand,
      })
        .then((r) => !cancelled && (setResult(r), setError(null)))
        .catch(() => !cancelled && setError(t('hp_view.error')));
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [
    pump,
    sourceIn,
    sourceOut,
    sinkIn,
    sinkOut,
    tMin,
    t,
    sourceProfile,
    sinkProfile,
    grid.source,
    grid.sink,
    point.Q_demand,
  ]);

  const reset = () => {
    setGrid(startGrid);
    setFixed(startFixed);
    setEditing(null);
    setPump(startPump);
  };
  const edit = (k: Temp, raw: string) => {
    setEditing({ k, raw });
    const v = parseFloat(raw.replace(',', '.'));
    if (!Number.isFinite(v)) return;
    if (searched(k)) setGrid((g) => ({ ...g, [SIDE[k]]: v }));
    else setFixed((f) => ({ ...f, [k]: v }));
  };
  const toggle = (k: Temp) =>
    onSearchTemps(searched(k) ? searchTemps.filter((s) => s !== API[k]) : [...searchTemps, API[k]]);

  // Only what the 2-temperature model reads: source out and sink out ranges.
  const rangeChecks = result?.checks.filter((c) => c.code.endsWith('_range')) ?? [];
  const cop = result?.cop_2t;
  // The optimization's own steps: the demand above the sink position off the
  // sink profile, the waste heat down to the source position off the source
  // profile, and whether the COP makes them meet.
  // Read off the profiles by the backend with the COP. Until its first answer
  // the view stands on the optimization's own point, which lies on both.
  const atPoint = grid.source === point.T_source && grid.sink === point.T_sink;
  const qSink = result ? (result.q_sink ?? null) : atPoint ? point.Q_demand : null;
  const qAvailable = result ? (result.q_available ?? null) : atPoint ? point.Q_source : null;
  const bal = cop != null ? (result?.balance ?? null) : null;
  const pEl = bal ? bal.p_el : null;
  const qSource = bal ? bal.needed : null;
  const kw = (v: number | null) => (v === null ? '–' : `${v.toFixed(1)} kW`);
  const range = (p: Profile) => [Math.min(...p.T), Math.max(...p.T)] as const;
  type Slider = { side: Side; color: string; r: readonly [number, number] };
  const sliders = (
    [
      { side: 'source', color: SOURCE, r: range(sourceProfile) },
      { side: 'sink', color: SINK, r: range(sinkProfile) },
    ] as Slider[]
  ).filter((s) => Number.isFinite(s.r[0]) && s.r[1] > s.r[0]);

  const field = (k: Temp, x: number, y: number, color: string) => (
    <foreignObject x={x} y={y} width={200} height={72}>
      {/* Out of the tab order while the model is shown and the pump faded. */}
      <div className="hpv-temp" style={{ color }} inert={morph >= 0.5}>
        <div className="hpv-name">
          T<sub>{t(`hp_view.sub.${k}`)}</sub>
          <label
            className={`hpv-badge ${searched(k) ? 'hpv-searched' : ''}`}
            title={t('hp_view.toggle_hint')}
          >
            <input
              type="checkbox"
              checked={searched(k)}
              onChange={() => toggle(k)}
              aria-label={t('hp_view.search_this', { name: `T ${t(`hp_view.sub.${k}`)}` })}
            />
            {searched(k) ? t('hp_view.searched') : t('hp_view.fixed')}
          </label>
        </div>
        <div className="hpv-german">{GERMAN[k]}</div>
        <label className="hpv-value">
          <input
            type="text"
            inputMode="decimal"
            value={editing?.k === k ? editing.raw : value(k).toFixed(1)}
            onChange={(e) => edit(k, e.target.value)}
            onBlur={() => setEditing(null)}
            style={{ color }}
            aria-label={t(`hp_view.name.${k}`)}
          />
          °C
        </label>
      </div>
    </foreignObject>
  );
  const arrow = (id: string, color: string) => (
    <marker
      id={id}
      viewBox="0 0 10 10"
      refX="9"
      refY="5"
      markerWidth="12"
      markerHeight="12"
      markerUnits="userSpaceOnUse"
      orient="auto"
    >
      <path d="M0,0 L10,5 L0,10 z" fill={color} />
    </marker>
  );

  // What the trained 2-temperature model reads: the two temperatures, the
  // refrigerant with its number of compressors (one column, e.g. "Butane_2")
  // and the sink medium. Compressors sit above the refrigerant so their paths
  // (from the compressor at the top, from the name below the COP) never cross. Each starts where it sits in the heat pump drawing
  // and ends as a circle in front of the model; the COP moves from the middle
  // of the pump to the model's output.
  const [refrigerantName, stages] = (() => {
    const name = pump?.refrigerant ?? '';
    const cut = name.lastIndexOf('_');
    return cut > 0 ? [name.slice(0, cut), name.slice(cut + 1)] : [name, '–'];
  })();
  const pumpOpacity = 1 - smooth(0.3, 0.7, morph);
  const modelOpacity = smooth(0.55, 0.9, morph);
  const travel = smooth(0.05, 0.85, morph);
  const inputY = (i: number) => 56 + i * 82;
  type Input = {
    key: string;
    color: string;
    from: [number, number];
    symbol: ReactNode;
    value: string;
    name: string;
    column: string;
  };
  const tempSymbol = (k: Temp) => (
    <>
      T
      <tspan baselineShift="sub" fontSize="10">
        {t(`hp_view.sub.${k}`)}
      </tspan>
    </>
  );
  const inputs: Input[] = [
    {
      key: 'sourceOut',
      color: SOURCE,
      from: [90, 82],
      symbol: tempSymbol('sourceOut'),
      value: `${temps.sourceOut.toFixed(1)} °C`,
      name: t('hp_view.name.sourceOut'),
      column: GERMAN_COLUMN.sourceOut,
    },
    {
      key: 'sinkOut',
      color: SINK,
      from: [840, 82],
      symbol: tempSymbol('sinkOut'),
      value: `${temps.sinkOut.toFixed(1)} °C`,
      name: t('hp_view.name.sinkOut'),
      column: GERMAN_COLUMN.sinkOut,
    },
    {
      key: 'stages',
      color: FLUID,
      from: [500, 75],
      symbol: t('hp_view.model.stages'),
      value: stages,
      name: t('hp_view.model.stages'),
      column: 'Kältemittel_stufen',
    },
    {
      key: 'refrigerant',
      color: FLUID,
      from: [500, 248],
      symbol: t('hp_view.model.refrigerant'),
      value: refrigerantName || '–',
      name: t('hp_view.model.refrigerant'),
      column: 'Kältemittel_stufen',
    },
    {
      key: 'medium',
      color: SINK,
      from: [880, 330],
      // The full name ("Sink medium") is beside the circle; inside, the short one.
      symbol: t('hp_view.model.medium_short'),
      value: pump?.medium_sink ?? '–',
      name: t('hp_view.model.medium'),
      column: 'Medium_Senke',
    },
  ];
  // One circle at full size (radius INPUT_R), drawn around (0, 0): moved and
  // scaled by its group, so it grows as it travels.
  const bubble = (color: string, r: number, symbol: ReactNode, value: string, big = false) => (
    <>
      <circle r={r} className="hpm-input" stroke={color} />
      <text y={big ? -8 : -6} textAnchor="middle" className="hpm-symbol" fill={color}>
        {symbol}
      </text>
      <text
        y={big ? 20 : 14}
        textAnchor="middle"
        className={big ? 'hpv-cop' : 'hpm-value'}
        fill={color}
      >
        {value}
      </text>
    </>
  );

  return (
    <div className="cf-backdrop" role="presentation" onClick={onClose}>
      <div
        className="cf-modal hpv-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t('hp_view.title')}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="cf-header">
          <h3>{t('hp_view.title')}</h3>
          <button className="cf-close" onClick={onClose} aria-label={t('cop_modal.close')}>
            <X size={16} />
          </button>
        </header>

        <div className="cf-body">
          <SearchSize />
          <div className="hpv-morph">
            <button type="button" className="hpv-morph-end" onClick={() => glide(0)}>
              {t('hp_view.tab_pump')}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={morph}
              onChange={(e) => {
                cancelAnimationFrame(glideFrame.current);
                setMorph(Number(e.target.value));
              }}
              aria-label={t('hp_view.morph_label')}
              aria-valuetext={morph < 0.5 ? t('hp_view.tab_pump') : t('hp_view.tab_model')}
            />
            <button type="button" className="hpv-morph-end" onClick={() => glide(1)}>
              {t('hp_view.tab_model')}
            </button>
          </div>
          <div className="hpv-toolbar">
            <span className="cf-muted">{t('hp_view.scale', { half: half.toFixed(1) })}</span>
          </div>

          <svg
            className="hpv-diagram"
            viewBox="0 0 1000 450"
            role="img"
            aria-label={morph < 0.5 ? t('hp_view.tab_pump') : t('hp_view.tab_model')}
          >
            <defs>
              {arrow('hpv-a-src', SOURCE)}
              {arrow('hpv-a-snk', SINK)}
              {arrow('hpv-a-fl', FLUID)}
              {arrow('hpm-a', '#64748B')}
            </defs>

            {/* The heat pump, fading out as the slider moves to the model. Its
                fields can be typed in only while it is the one shown. */}
            {pumpOpacity > 0 && (
              <g opacity={pumpOpacity} style={{ pointerEvents: morph < 0.5 ? 'auto' : 'none' }}>
                {[
                  [10, 330, t('hp_view.circuit1')],
                  [345, 310, t('hp_view.circuit2')],
                  [670, 320, t('hp_view.circuit3')],
                ].map(([x, w, label]) => (
                  <g key={String(label)}>
                    <text
                      x={Number(x) + Number(w) / 2}
                      y={22}
                      textAnchor="middle"
                      className="hpv-circuit"
                    >
                      {label}
                    </text>
                    <rect
                      x={Number(x)}
                      y={36}
                      width={Number(w)}
                      height={384}
                      className="hpv-frame"
                    />
                  </g>
                ))}

                {/* waste heat: in at the bottom, out at the top */}
                <polyline
                  points="30,330 235,330 235,262"
                  className="hpv-pipe"
                  stroke={SOURCE}
                  markerEnd="url(#hpv-a-src)"
                />
                <polyline
                  points="235,168 235,110 30,110"
                  className="hpv-pipe"
                  stroke={SOURCE}
                  markerEnd="url(#hpv-a-src)"
                />
                {/* process heat */}
                <polyline
                  points="970,330 765,330 765,262"
                  className="hpv-pipe"
                  stroke={SINK}
                  markerEnd="url(#hpv-a-snk)"
                />
                <polyline
                  points="765,168 765,110 970,110"
                  className="hpv-pipe"
                  stroke={SINK}
                  markerEnd="url(#hpv-a-snk)"
                />
                {/* refrigerant: evaporator → compressor → condenser → valve */}
                <polyline points="290,168 290,75 474,75" className="hpv-pipe" stroke={FLUID} />
                <polyline
                  points="526,75 712,75 712,166"
                  className="hpv-pipe"
                  stroke={FLUID}
                  markerEnd="url(#hpv-a-fl)"
                />
                <polyline points="712,262 712,370 520,370" className="hpv-pipe" stroke={FLUID} />
                <polyline
                  points="480,370 290,370 290,264"
                  className="hpv-pipe"
                  stroke={FLUID}
                  markerEnd="url(#hpv-a-fl)"
                />
                <circle cx={500} cy={75} r={26} className="hpv-box" stroke={FLUID} />
                <text x={500} y={81} textAnchor="middle" className="hpv-c" fill={FLUID}>
                  C
                </text>
                <path
                  d="M480,358 L500,370 L480,382 Z M520,358 L500,370 L520,382 Z"
                  className="hpv-box"
                  stroke={FLUID}
                />
                <text x={500} y={402} textAnchor="middle" className="hpv-small" fill={FLUID}>
                  {t('hp_view.valve')}
                </text>
                <text x={538} y={104} className="hpv-label" fill={FLUID}>
                  {t('hp_view.compressor')}
                </text>
                <text x={538} y={124} className="hpv-label" fill={FLUID}>
                  P
                  <tspan baselineShift="sub" fontSize="11">
                    el
                  </tspan>{' '}
                  {kw(pEl)}
                </text>

                <rect
                  x={180}
                  y={168}
                  width={150}
                  height={94}
                  className="hpv-box"
                  stroke="#181C62"
                />
                <text x={255} y={207} textAnchor="middle" className="hpv-label">
                  {t('hp_view.evaporator')}
                </text>
                <text x={255} y={230} textAnchor="middle" className="hpv-label" fill={SOURCE}>
                  Q
                  <tspan baselineShift="sub" fontSize="11">
                    source
                  </tspan>{' '}
                  {kw(qSource)}
                </text>
                <rect
                  x={670}
                  y={168}
                  width={150}
                  height={94}
                  className="hpv-box"
                  stroke="#181C62"
                />
                <text x={745} y={207} textAnchor="middle" className="hpv-label">
                  {t('hp_view.condenser')}
                </text>
                <text x={745} y={230} textAnchor="middle" className="hpv-label" fill={SINK}>
                  Q
                  <tspan baselineShift="sub" fontSize="11">
                    sink
                  </tspan>{' '}
                  {kw(qSink)}
                </text>

                <text x={500} y={200} textAnchor="middle" className="hpv-cop">
                  {cop ? `COP ${cop.toFixed(2)}` : 'COP –'}
                </text>
                <text x={500} y={226} textAnchor="middle" className="hpv-small">
                  {t('hp_view.case_2t')}
                </text>
                {pump && (
                  <text x={500} y={248} textAnchor="middle" className="hpv-small">
                    {pump.refrigerant} · {pump.medium_sink}
                  </text>
                )}

                {field('sourceOut', 30, 38, SOURCE)}
                {field('sinkOut', 780, 38, SINK)}
              </g>
            )}

            {/* The model: a rectangle, its inputs' names and columns, the links. */}
            {modelOpacity > 0 && (
              <g opacity={modelOpacity}>
                <text x={INPUT_X} y={16} textAnchor="middle" className="hpm-head">
                  {t('hp_view.model.inputs')}
                </text>
                <text
                  x={OUTPUT.x}
                  y={OUTPUT.y - OUTPUT.r - 16}
                  textAnchor="middle"
                  className="hpm-head"
                >
                  {t('hp_view.model.output')}
                </text>
                {inputs.map((v, i) => (
                  <g key={v.key}>
                    <text
                      x={INPUT_X - INPUT_R - 14}
                      y={inputY(i) - 2}
                      textAnchor="end"
                      className="hpm-name"
                    >
                      {v.name}
                    </text>
                    <text
                      x={INPUT_X - INPUT_R - 14}
                      y={inputY(i) + 14}
                      textAnchor="end"
                      className="hpm-column"
                    >
                      {v.column}
                    </text>
                    <path
                      d={`M${INPUT_X + INPUT_R} ${inputY(i)} C ${INPUT_X + 110} ${inputY(i)}, ${
                        MODEL.x - 80
                      } ${lerp(MODEL.y + 25, MODEL.y + MODEL.h - 25, i / (inputs.length - 1))}, ${
                        MODEL.x - 4
                      } ${lerp(MODEL.y + 25, MODEL.y + MODEL.h - 25, i / (inputs.length - 1))}`}
                      className="hpv-pipe hpm-link"
                      markerEnd="url(#hpm-a)"
                    />
                  </g>
                ))}
                <rect
                  x={MODEL.x}
                  y={MODEL.y}
                  width={MODEL.w}
                  height={MODEL.h}
                  rx={12}
                  className="hpm-model"
                  stroke={FLUID}
                />
                <text
                  x={MODEL.x + MODEL.w / 2}
                  y={MODEL.y + MODEL.h / 2 - 6}
                  textAnchor="middle"
                  className="hpm-model-name"
                  fill={FLUID}
                >
                  {t('hp_view.model.name')}
                </text>
                <text
                  x={MODEL.x + MODEL.w / 2}
                  y={MODEL.y + MODEL.h / 2 + 18}
                  textAnchor="middle"
                  className="hpv-small"
                >
                  {t('hp_view.model.kind_2t')}
                </text>
                <text
                  x={MODEL.x + MODEL.w / 2}
                  y={MODEL.y + MODEL.h + 22}
                  textAnchor="middle"
                  className="hpm-column"
                >
                  {t('hp_view.model.one_column_note')}
                </text>
                <path
                  d={`M${MODEL.x + MODEL.w} ${OUTPUT.y} L ${OUTPUT.x - OUTPUT.r - 4} ${OUTPUT.y}`}
                  className="hpv-pipe"
                  stroke={FLUID}
                  markerEnd="url(#hpv-a-fl)"
                />
                <text
                  x={OUTPUT.x}
                  y={OUTPUT.y + OUTPUT.r + 22}
                  textAnchor="middle"
                  className="hpv-small"
                >
                  {t('hp_view.model.cop_name')}
                </text>
                <text x={500} y={440} textAnchor="middle" className="hpm-meaning">
                  {cop != null
                    ? t('hp_view.model.cop_meaning', { cop: cop.toFixed(2) })
                    : t('hp_view.model.cop_meaning_none')}
                </text>
              </g>
            )}

            {/* The variables on their way: each a circle that grows as it moves
                from its place in the pump to its place at the model. */}
            {morph > 0 && (
              // Only a picture: the circles pass over the pump's fields and
              // must not take their clicks.
              <g opacity={smooth(0, 0.15, morph)} style={{ pointerEvents: 'none' }}>
                {inputs.map((v, i) => (
                  <g
                    key={v.key}
                    transform={`translate(${lerp(v.from[0], INPUT_X, travel)} ${lerp(
                      v.from[1],
                      inputY(i),
                      travel
                    )}) scale(${lerp(0.45, 1, travel)})`}
                  >
                    {bubble(v.color, INPUT_R, v.symbol, v.value)}
                  </g>
                ))}
                <g
                  transform={`translate(${lerp(500, OUTPUT.x, travel)} ${lerp(205, OUTPUT.y, travel)}) scale(${lerp(
                    0.6,
                    1,
                    travel
                  )})`}
                >
                  {bubble(FLUID, OUTPUT.r, 'COP', cop != null ? cop.toFixed(2) : '–', true)}
                </g>
              </g>
            )}
          </svg>

          <div className="hpv-calc-row">
            <section className="hpv-search">
              <h4>{t('hp_view.search_title')}</h4>
              <label className="hpv-slider">
                <span>{t('hp_view.pump')}</span>
                <select
                  value={pump ? `${pump.refrigerant}|${pump.medium_sink}` : ''}
                  onChange={(e) => {
                    const [refrigerant, medium_sink] = e.target.value.split('|');
                    setPump({ refrigerant, medium_sink });
                  }}
                >
                  {pumps.map((p) => (
                    <option
                      key={`${p.refrigerant}|${p.medium_sink}`}
                      value={`${p.refrigerant}|${p.medium_sink}`}
                    >
                      {p.refrigerant} · {p.medium_sink}
                    </option>
                  ))}
                </select>
              </label>
              {sliders.map(({ side, color, r }) => {
                const follow = TEMPS.filter((k) => SIDE[k] === side && searched(k));
                return (
                  <label key={side} className="hpv-slider" style={{ color }}>
                    <span>
                      {t(`hp_view.search_${side}`)} {grid[side].toFixed(1)} °C
                    </span>
                    <input
                      type="range"
                      min={r[0]}
                      max={r[1]}
                      step={0.1}
                      value={Math.min(r[1], Math.max(r[0], grid[side]))}
                      onChange={(e) => {
                        setEditing(null);
                        setGrid((g) => ({ ...g, [side]: parseFloat(e.target.value) }));
                      }}
                      style={{ accentColor: color }}
                    />
                    <span className="cf-muted">
                      {r[0].toFixed(1)} – {r[1].toFixed(1)} °C {t('hp_view.along_profile')} ·{' '}
                      {follow.length
                        ? t('hp_view.follows', {
                            names: follow.map((k) => `T ${t(`hp_view.sub.${k}`)}`).join(', '),
                          })
                        : t('hp_view.follows_none')}
                    </span>
                  </label>
                );
              })}
            </section>

            <section className="hpv-calc">
              <h4>{t('hp_view.calc_title')}</h4>
              <ol>
                <li>
                  {t('hp_view.step_qsink', { t: grid.sink.toFixed(1) })} <b>{kw(qSink)}</b>
                </li>
                <li>
                  {t('hp_view.step_cop', { name: t('hp_view.case_2t') })}{' '}
                  <b>{cop != null ? cop.toFixed(2) : '–'}</b>
                </li>
                <li>
                  {t('hp_view.step_needed')} <code>Q_sink · (COP − 1) / COP</code> ={' '}
                  <b>{kw(bal ? bal.needed : null)}</b>
                </li>
                <li>
                  {t('hp_view.step_available', { t: grid.source.toFixed(1) })}{' '}
                  <b>{kw(qAvailable)}</b>
                </li>
                <li>
                  {t('hp_view.step_pel')} <code>Q_sink / COP</code> = <b>{kw(pEl)}</b>
                </li>
              </ol>
              {bal && (
                <p className={`hpv-verdict hpv-${bal.state}`}>
                  {t(`hp_view.state.${bal.state}`, {
                    gap: Math.abs(bal.gap).toFixed(1),
                    possible: bal.q_sink_possible.toFixed(1),
                  })}
                </p>
              )}
            </section>
          </div>

          <p className="cf-muted hpv-note">{t('hp_view.optimization_note')}</p>

          {error && <p className="hpv-warn">{error}</p>}
          {rangeChecks.length > 0 && (
            <ul className="hpv-warn">
              {rangeChecks.map((c) => (
                <li key={c.code}>
                  {t(`hp_view.check.${c.code}`, {
                    value: c.value?.toFixed(1),
                    min: c.min?.toFixed(0),
                    max: c.max?.toFixed(0),
                  })}
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="cf-footer">
          <button className="cf-btn" onClick={reset}>
            {t('hp_view.reset')}
          </button>
          <span className="cf-spacer" />
          <button className="cf-btn cf-btn-primary" onClick={onClose}>
            {t('hp_view.close')}
          </button>
        </footer>
      </div>
    </div>
  );
}
