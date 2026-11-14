/**
 * A stream's values for the map, the stream table and the labels: what the
 * analysis reads (getStreamInfo, held to the backend's stream_info by
 * tests/fixtures/stream_info_reference.json), with hot/cold as a short type
 * and the extra properties entered with the stream.
 */
import type { Stream } from '../types/stream';
import { getStreamInfo } from './streamUtils';

export interface StreamInfo {
  tin: number | null;
  tout: number | null;
  mdot: number | null;
  cp: number | null;
  CP: number | null;
  Q: number | null;
  type: 'hot' | 'cold' | null;
  density: string | null;
  pressure: string | null;
  water_in: string | null;
  water_out: string | null;
}

export function extractStreamInfo(stream: Record<string, any>): StreamInfo {
  const info = getStreamInfo(stream as Stream);
  const sv: Record<string, any> = stream.stream_values || {};
  const type: StreamInfo['type'] =
    info.tin != null && info.tout != null ? (info.tin > info.tout ? 'hot' : 'cold') : null;
  return {
    tin: info.tin,
    tout: info.tout,
    mdot: info.mdot,
    cp: info.cp,
    CP: info.CP,
    Q: info.Q,
    type,
    density: sv.Density || null,
    pressure: sv.Pressure || null,
    water_in: sv['Water Content In'] || null,
    water_out: sv['Water Content Out'] || null,
  };
}

// A subscript moved down and back up with dy, which every browser draws the same;
// the rest of the value follows in the tspan it opens (closed by `after`).
const sub = (s: string) => `<tspan dy="3" font-size="75%">${s}</tspan><tspan dy="-3">`;
const after = (s: string) => `${s}</tspan>`;
const known = (v: number | null | undefined): v is number => v !== null && v !== undefined;

/** A stream's values as SVG text for the map labels, with subscripts and units
 *  (the values are already in °C, kg/s and kJ/(kg·K)); empty where unknown. */
export function streamSvgText(info: Pick<StreamInfo, 'tin' | 'tout' | 'mdot' | 'cp'>) {
  return {
    tin: known(info.tin) ? `T${sub('in')}${after(`=${info.tin} °C`)}` : '',
    tout: known(info.tout) ? `T${sub('out')}${after(`=${info.tout} °C`)}` : '',
    mdot: known(info.mdot) ? `ṁ=${info.mdot} kg/s` : '',
    cp: known(info.cp) ? `c${sub('p')}${after(`=${info.cp} kJ/(kg·K)`)}` : '',
  };
}

/** About how wide an SVG label line is at 11 px, for sizing its box. */
export const svgTextWidth = (svg: string) => svg.replace(/<[^>]+>/g, '').length * 6.3;
