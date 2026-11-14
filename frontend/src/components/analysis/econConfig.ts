/** Inputs of the economic analysis: defaults, presets, the input form's
 *  fields, and which results go where. */

import type { OptimizedIntegrationPoint } from '../../types/analysis';

// The inputs, in the order of the form. Their default values and the
// reference heater presets come from the backend (GET
// /api/analysis/economics/defaults, backend/app/services/economics/model.py),
// the one place they are kept; each value, its source and why it may differ:
// data/economic_calculation/economic_analysis_rationale.md.
// Display units: prices in ct/kWh, rates and shares in %.
export const FORM_KEYS = [
  'year',
  'hours',
  'i',
  'T',
  'eta',
  'hsHi',
  'pFuel',
  'rFuel',
  'co2Fuel',
  'co2Price',
  'rCo2',
  'boilerInvest',
  'fMaintRef',
  'pEl',
  'rEl',
  'co2El',
  'co2ElPriced',
  'co2e',
  'co2eFuel',
  'co2eEl',
  'pDemand',
  'specCost',
  'fPI',
  'fPer',
  'fMaint',
  'opHours',
  'wage',
  'reinvestShare',
  'reinvestYear',
  'life',
  'rInv',
  'funding',
  'opFunding',
  'opFundingYears',
  'coolShare',
  'eer',
] as const;
export type FormKey = (typeof FORM_KEYS)[number];
export type Form = Record<FormKey, number>;

// Reference heaters: picking one loads its efficiency, price and CO₂ factor,
// all editable afterwards.
export type RefType = 'gas' | 'oil' | 'eboiler';
export const REF_TYPES: RefType[] = ['gas', 'oil', 'eboiler'];
export type Preset = Pick<Form, 'eta' | 'hsHi' | 'pFuel' | 'co2Fuel' | 'co2eFuel'>;

/** What GET /api/analysis/economics/defaults answers. */
export interface EconDefaults {
  form: Form;
  presets: Record<RefType, Preset>;
}

export type Group =
  'general' | 'reference' | 'electricity' | 'hp' | 'funding' | 'cooling' | 'replace';
export const GROUPS: Group[] = [
  'general',
  'reference',
  'electricity',
  'hp',
  'funding',
  'cooling',
  'replace',
];
// Yes/no inputs, shown as a checkbox and stored as 0 / 1.
export const BOOL_FIELDS: Array<keyof Form> = ['co2ElPriced', 'co2e'];

// Options that are off by default (value 0). A checkbox switches one on, which
// fills in a typical value, taken from its help text; off sets 0 again.
export const SWITCHES: Partial<Record<keyof Form, number>> = {
  pDemand: 100, // industrial capacity charges: often 50–150 €/kW per year
  reinvestShare: 20, // e.g. a compressor overhaul; an assumption, no source
  opFunding: 92, // BEW Modul 4: up to about 92 €/MWh
  coolShare: 100, // a chiller or cooling tower removes all of it today
  boilerInvest: 200, // user decision 2026-11-09; VDI 4646:2026 (p. 74) has 131
};
// Inputs that only count while an option is on: greyed out while it is off.
export const SWITCHED_BY: Partial<Record<keyof Form, keyof Form>> = {
  reinvestYear: 'reinvestShare',
  opFundingYears: 'opFunding',
  eer: 'coolShare',
  fMaintRef: 'boilerInvest',
  co2eFuel: 'co2e',
  co2eEl: 'co2e',
};

export type Range = { step: number; min: number; max: number; open?: boolean };

// Inputs: key, unit, the block it sits in, and the step and range of the −/+
// buttons and slider.
// "open" ranges have no natural upper bound: releasing the slider at its end
// doubles the range, so dragging again goes further. Typed values beyond the
// range stretch it too. Physical limits (efficiency, hours, shares) stay closed.
export const FIELDS: Array<[keyof Form, string, Group, Range]> = [
  ['year', 'a', 'general', { step: 1, min: 2025, max: 2045 }],
  ['hours', 'h/a', 'general', { step: 100, min: 0, max: 8760 }],
  ['i', '%', 'general', { step: 0.5, min: 0, max: 15, open: true }],
  ['T', 'a', 'general', { step: 1, min: 1, max: 40, open: true }],
  ['co2e', '-', 'general', { step: 1, min: 0, max: 1 }],
  ['eta', '%', 'reference', { step: 1, min: 50, max: 100 }],
  ['hsHi', '-', 'reference', { step: 0.01, min: 1, max: 1.2 }],
  ['pFuel', 'ct/kWh', 'reference', { step: 0.5, min: 0, max: 30, open: true }],
  ['rFuel', '%/a', 'reference', { step: 0.5, min: -5, max: 10, open: true }],
  ['co2Fuel', 't/MWh', 'reference', { step: 0.001, min: 0, max: 0.4 }],
  ['co2eFuel', 't/MWh', 'reference', { step: 0.01, min: 0, max: 1 }],
  ['co2Price', '€/t', 'reference', { step: 5, min: 0, max: 300, open: true }],
  ['rCo2', '%/a', 'reference', { step: 0.5, min: -5, max: 15, open: true }],
  ['pEl', 'ct/kWh', 'electricity', { step: 0.5, min: 0, max: 40, open: true }],
  ['rEl', '%/a', 'electricity', { step: 0.5, min: -5, max: 10, open: true }],
  ['co2El', 't/MWh', 'electricity', { step: 0.01, min: 0, max: 1 }],
  ['co2eEl', 't/MWh', 'electricity', { step: 0.01, min: 0, max: 1 }],
  ['co2ElPriced', '-', 'electricity', { step: 1, min: 0, max: 1 }],
  ['pDemand', '€/kW/a', 'hp', { step: 10, min: 0, max: 300, open: true }],
  ['specCost', '€/kW', 'hp', { step: 10, min: 0, max: 2500, open: true }],
  ['fPI', '-', 'hp', { step: 0.05, min: 1, max: 3, open: true }],
  ['fPer', '-', 'hp', { step: 0.05, min: 1, max: 3, open: true }],
  ['fMaint', '%/a', 'hp', { step: 0.5, min: 0, max: 10, open: true }],
  ['opHours', 'h/a', 'hp', { step: 1, min: 0, max: 100, open: true }],
  ['wage', '€/h', 'hp', { step: 5, min: 0, max: 200, open: true }],
  ['reinvestShare', '%', 'hp', { step: 5, min: 0, max: 100 }],
  ['reinvestYear', 'a', 'hp', { step: 1, min: 1, max: 40, open: true }],
  ['life', 'a', 'hp', { step: 1, min: 0, max: 50, open: true }],
  ['rInv', '%/a', 'hp', { step: 0.5, min: -5, max: 10, open: true }],
  ['funding', '%', 'hp', { step: 5, min: 0, max: 100 }],
  ['opFunding', '€/MWh', 'funding', { step: 5, min: 0, max: 100, open: true }],
  ['opFundingYears', 'a', 'funding', { step: 1, min: 0, max: 20, open: true }],
  ['coolShare', '%', 'cooling', { step: 5, min: 0, max: 100 }],
  ['eer', '-', 'cooling', { step: 0.5, min: 1, max: 40, open: true }],
  ['boilerInvest', '€/kW', 'replace', { step: 10, min: 0, max: 500, open: true }],
  ['fMaintRef', '%/a', 'replace', { step: 0.5, min: 0, max: 10, open: true }],
];

export const pointKey = (p: OptimizedIntegrationPoint) =>
  `${p.refrigerant}|${p.T_source}|${p.T_sink}`;
export const pointName = (p: OptimizedIntegrationPoint) =>
  `${p.refrigerant} ${p.T_sink.toFixed(0)} °C`;

// The results shown up front, one line per pump.
export const KPI_ROWS = ['payback', 'npv', 'lcoh_hp', 'co2_saving', 'breakeven'];
// One colour per key result, none of them the pinch cards' red, blue, violet
// or green, so the two rows of cards read as different things.
export const KPI_COLORS: Record<string, string> = {
  lcoh_hp: '#B45309', // amber
  payback: '#0F766E', // teal
  npv: '#A21CAF', // fuchsia
  co2_saving: '#475569', // slate
  breakeven: '#7C2D12', // brown
};

// Which result rows go in which of the two result tables.
export const RESULT_ROWS_ENERGY = [
  'q',
  'qsrc',
  'cop',
  'fuel',
  'el',
  'elCool',
  'energy_saving',
  'co2',
  'co2_saving',
  'alpha',
];
export const RESULT_ROWS_MONEY = [
  'opex1',
  'saving1',
  'payback',
  'payback_static',
  'residual',
  'npv',
  'irr',
  'lcoh_hp',
  'lcoh_ref',
  'breakeven',
  'spec_total',
  'capex_vdi',
];

// Loss / gain, used wherever a value's sign matters.
export const RED = '#C62828';
export const GREEN = '#2E7D32';
// Rows whose cells are coloured by sign.
export const SIGNED_ROWS = new Set(['saving1', 'energy_saving', 'co2_saving', 'npv', 'irr']);
