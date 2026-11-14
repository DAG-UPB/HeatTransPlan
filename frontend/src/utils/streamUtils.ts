/**
 * A stream's inlet/outlet temperature (°C), mass flow (kg/s), cp (kJ/(kg·K)),
 * CP (kW/K) and duty Q (kW), whichever way it was entered. The page reads
 * streams with this, the backend with app/services/project_analysis.py
 * stream_info: both are held to tests/fixtures/stream_info_reference.json
 * (streamUtils.test.ts here, tests/test_project_analysis.py there).
 */

import type { ProcessNode } from '../types/process';
import type { Stream } from '../types/stream';
import type { StreamInfo } from '../types/analysis';

function toFloat(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function getStreamInfo(stream: Stream): StreamInfo {
  const sv = stream.stream_values ?? {};
  const properties = stream.properties ?? {};
  const values = stream.values ?? {};

  let tin: number | null = null;
  let tout: number | null = null;
  let mdot: number | null = null;
  let cpVal: number | null = null;
  let cpDirect: number | null = null;

  const units = stream.stream_units ?? {};

  const convertTemp = (val: number | null, unit: string | undefined): number | null => {
    if (val === null) return null;
    if (unit === '°F') return ((val - 32) * 5) / 9;
    if (unit === 'K') return val - 273.15;
    return val; // default °C
  };

  const convertMdot = (val: number | null, unit: string | undefined): number | null => {
    if (val === null) return null;
    if (unit === 'kg/min') return val / 60;
    if (unit === 'kg/h') return val / 3600;
    if (unit === 't/min') return (val * 1000) / 60;
    if (unit === 't/h') return (val * 1000) / 3600;
    if (unit === 't/d') return (val * 1000) / (24 * 3600);
    return val; // default kg/s
  };

  const convertCp = (val: number | null, unit: string | undefined): number | null => {
    if (val === null) return null;
    if (unit === 'J/(kg·K)') return val / 1000;
    return val; // default kJ/(kg·K)
  };

  const convertCPDirect = (val: number | null, unit: string | undefined): number | null => {
    if (val === null) return null;
    if (unit === 'W/K') return val / 1000;
    return val; // default kW/K
  };

  // 1. Try stream_values (new structure)
  if (sv) {
    tin = convertTemp(toFloat(sv['Tin']), units['Tin']);
    tout = convertTemp(toFloat(sv['Tout']), units['Tout']);
    mdot = convertMdot(toFloat(sv['ṁ']), units['ṁ']);
    cpVal = convertCp(toFloat(sv['cp']), units['cp']);
    cpDirect = convertCPDirect(toFloat(sv['CP']), units['CP']);
  }

  // 2. Check properties/values dict structure.
  // Units are keyed by variable name, so they apply here too — reading these
  // raw treated a value entered in °F or kg/h as if it were °C or kg/s.
  if (properties && values) {
    for (const [pk, pname] of Object.entries(properties)) {
      const vk = pk.replace('prop', 'val');
      const v = (values as Record<string, string>)[vk] ?? '';
      if (pname === 'Tin' && v && tin === null) tin = convertTemp(toFloat(v), units['Tin']);
      else if (pname === 'Tout' && v && tout === null)
        tout = convertTemp(toFloat(v), units['Tout']);
      else if (pname === 'ṁ' && v && mdot === null) mdot = convertMdot(toFloat(v), units['ṁ']);
      else if (pname === 'cp' && v && cpVal === null) cpVal = convertCp(toFloat(v), units['cp']);
      else if (pname === 'CP' && v && cpDirect === null)
        cpDirect = convertCPDirect(toFloat(v), units['CP']);
    }
  }

  // 3. Fallback to legacy fields
  if (tin === null && stream.temp_in) tin = convertTemp(toFloat(stream.temp_in), units['Tin']);
  if (tout === null && stream.temp_out) tout = convertTemp(toFloat(stream.temp_out), units['Tout']);
  if (mdot === null && stream.mdot) mdot = convertMdot(toFloat(stream.mdot), units['ṁ']);
  if (cpVal === null && stream.cp) cpVal = convertCp(toFloat(stream.cp), units['cp']);

  // Determine stream type
  let type: StreamInfo['type'] = null;
  if (tin !== null && tout !== null) {
    type = tin > tout ? 'Hot stream (Heat Source)' : 'Cold stream (Heat sink)';
  }

  // CP: use direct if provided, otherwise mdot * cp
  let CP: number | null = null;
  if (cpDirect !== null) {
    CP = cpDirect;
  } else if (mdot !== null && cpVal !== null) {
    CP = mdot * cpVal;
  }

  // Q = |CP * (Tout - Tin)|
  let Q: number | null = null;
  if (CP !== null && tin !== null && tout !== null) {
    Q = Math.abs(CP * (tout - tin));
  }

  return { tin, tout, mdot, cp: cpVal, CP, Q, type };
}

/** A selected stream as the analysis gets it. */
export interface AnalysisStream {
  name: string;
  CP: number;
  Tin: number;
  Tout: number;
  Q: number;
  type: 'Hot' | 'Cold';
}

/** The streams ticked in a selection ("stream_<subprocess>_<stream>" → on)
 *  that have inlet, outlet temperature and CP, named "<subprocess> - <stream>".
 *  The same as the backend's project_analysis.selected_streams (both held to
 *  tests/fixtures/selected_streams_reference.json). */
export function selectedStreams(
  processes: ProcessNode[],
  selection: Record<string, boolean>
): AnalysisStream[] {
  const result: AnalysisStream[] = [];
  for (const [key, selected] of Object.entries(selection)) {
    if (!selected || !key.startsWith('stream_')) continue;
    const parts = key.split('_');
    // Indices only: anything else names no stream.
    if (!/^\d+$/.test(parts[1] ?? '') || !/^\d+$/.test(parts[2] ?? '')) continue;
    const pIdx = parseInt(parts[1], 10);
    const sIdx = parseInt(parts[2], 10);
    if (pIdx >= processes.length) continue;
    const proc = processes[pIdx];
    const streams = proc.streams ?? [];
    if (sIdx >= streams.length) continue;
    const stream = streams[sIdx];
    const info = getStreamInfo(stream);
    if (info.tin !== null && info.tout !== null && info.CP !== null) {
      const procName = proc.name || `Subprocess ${pIdx + 1}`;
      const streamName = stream.name || `Stream ${sIdx + 1}`;
      result.push({
        name: `${procName} - ${streamName}`,
        CP: info.CP,
        Tin: info.tin,
        Tout: info.tout,
        Q: info.Q ?? 0,
        type: info.tin > info.tout ? 'Hot' : 'Cold',
      });
    }
  }
  return result;
}
