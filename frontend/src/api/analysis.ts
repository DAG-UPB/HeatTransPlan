/** API client for analysis endpoints. */

import client from './client';
import type {
  CopFormulaValidateResult,
  CopPointRequest,
  CopPointResult,
  HPIOptimizationRequest,
  HPIOptimizationResult,
  HPIRequest,
  HPIResult,
  PinchRequest,
  PinchResult,
  StatusQuoRequest,
  StatusQuoResult,
  OptimizedIntegrationPoint,
} from '../types/analysis';
import type { EconNumbers } from '../types/economics';
import type { EconDefaults } from '../components/analysis/econConfig';
import { useAnalysisStore } from '../store/analysisStore';

export async function runPinch(req: PinchRequest): Promise<PinchResult> {
  const { data } = await client.post<PinchResult>('/api/analysis/pinch', req);
  return data;
}

export async function runHPI(req: HPIRequest): Promise<HPIResult> {
  const { data } = await client.post<HPIResult>('/api/analysis/hpi', req);
  return data;
}

export async function runHPIOptimization(
  req: HPIOptimizationRequest
): Promise<HPIOptimizationResult> {
  const { data } = await client.post<HPIOptimizationResult>('/api/analysis/hpi-optimization', req);
  return data;
}

/** Check a COP formula and preview its value. Called as the user types, so it
 *  deliberately does not touch the optimisation. */
export async function validateCopFormula(
  expression: string,
  T_source = 60,
  T_sink = 110
): Promise<CopFormulaValidateResult> {
  const { data } = await client.post<CopFormulaValidateResult>(
    '/api/analysis/cop-formula/validate',
    { expression, T_source, T_sink }
  );
  return data;
}

/** Every heat pump the trained models know (the COP model page). */
/** One heat pump at four chosen temperatures, rated by both trained models
 *  and the Carnot reference (the heat pump view). */
export async function rateCopPoint(req: CopPointRequest): Promise<CopPointResult> {
  const { data } = await client.post<CopPointResult>('/api/analysis/cop-point', req);
  return data;
}

/** The economic analysis of the pump picked (or the default one). The real
 *  machines are sent, and the points of a theoretical pump's own archetype:
 *  the reference size and the size curve come from them; the other
 *  archetypes would only make the request heavier. */
export async function runEconomics(
  form: Record<string, number>,
  refType: string,
  selected: OptimizedIntegrationPoint[],
  opt: HPIOptimizationResult | null | undefined,
  sensBase: { fuel: number; el: number } | null = null
): Promise<EconNumbers | null> {
  const analysed = selected.length ? selected : opt?.max_q_point ? [opt.max_q_point] : [];
  const archetypes = new Set(analysed.filter((p) => p.theoretical).map((p) => p.refrigerant));
  const optimization = opt && {
    feasible_points: opt.feasible_points.filter(
      (p) => !p.theoretical || archetypes.has(p.refrigerant)
    ),
    max_q_point: opt.max_q_point,
  };
  const { data } = await client.post<EconNumbers | null>('/api/analysis/economics', {
    form,
    ref_type: refType,
    selected_points: selected,
    optimization,
    sens_base: sensBase,
  });
  return data;
}

export async function runStatusQuo(req: StatusQuoRequest): Promise<StatusQuoResult> {
  const { data } = await client.post<StatusQuoResult>('/api/analysis/status-quo', req);
  return data;
}

export async function generateReport(payload: Record<string, unknown>): Promise<Blob> {
  const { data } = await client.post('/api/analysis/report', payload, {
    responseType: 'blob',
  });
  return data as Blob;
}

export async function getMapPreview(
  payload: Record<string, unknown>
): Promise<{ map_b64: string }> {
  const { data } = await client.post<{ map_b64: string }>('/api/analysis/map-preview', payload);
  return data;
}

let econDefaultsPending: Promise<EconDefaults> | null = null;

/** The economic analysis' default inputs and reference heater presets, from
 *  the backend (the one place they are kept). Asked once; kept in the
 *  analysis store, where the inputs start from them. A failed request is
 *  asked again next time. */
export function loadEconDefaults(): Promise<EconDefaults> {
  const known = useAnalysisStore.getState().econDefaults;
  if (known) return Promise.resolve(known);
  econDefaultsPending ??= client
    .get<EconDefaults>('/api/analysis/economics/defaults')
    .then(({ data }) => {
      useAnalysisStore.getState().setEconDefaults(data);
      return data;
    })
    .finally(() => {
      econDefaultsPending = null;
    });
  return econDefaultsPending;
}
