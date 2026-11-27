/** Pins the whole economic analysis — tables, key results, summaries and every
 *  chart spec — for real optimization output, each reference system, both
 *  themes and both languages. A refactoring that moves a number, a colour or a
 *  word fails here. */

import { describe, it, expect, beforeEach } from 'vitest';
import i18n from '../../i18n';
import type { EconNumbers } from '../../types/economics';
import numbers from '../../test/fixtures/economics_numbers.json';
import { buildEconomics, econReportData } from './econModel';
import type { RefType } from './econConfig';
import { econDefaults } from '../../test/backendFixtures';
import { dump } from '../../test/dump';

// What the backend returns for each case (tests/test_economics.py proves
// those numbers equal the ones the page used to compute itself).
const N = numbers as unknown as Record<string, EconNumbers | null>;
const picks = ['none', 'one', 'several'];
const REFS: RefType[] = ['gas', 'oil', 'eboiler'];
// The backend's default inputs, as the page gets them.
const DEFAULTS = econDefaults().form;

beforeEach(async () => {
  await i18n.changeLanguage('en');
});

describe('economic model', () => {
  for (const ref of REFS) {
    for (const name of picks) {
      it(`buildEconomics ${ref} ${name}`, () => {
        expect(dump(buildEconomics(i18n.t, DEFAULTS, ref, N[`${ref}_${name}`]))).toMatchSnapshot();
      });
    }
  }

  it('dark theme and a fixed sensitivity window', () => {
    expect(dump(buildEconomics(i18n.t, DEFAULTS, 'gas', N.dark_sens, true))).toMatchSnapshot();
  });

  it('changed inputs', () => {
    const form = { ...DEFAULTS, specCost: 1500, funding: 40, co2ElPriced: 1, T: 15 };
    expect(dump(buildEconomics(i18n.t, form, 'oil', N.changed))).toMatchSnapshot();
  });

  it('German report data', async () => {
    await i18n.changeLanguage('de');
    expect(dump(econReportData(i18n.t, DEFAULTS, 'gas', N.gas_several))).toMatchSnapshot();
  });

  it('report data, core and pump choice', () => {
    expect(dump(econReportData(i18n.t, DEFAULTS, 'eboiler', N.eboiler_one))).toMatchSnapshot();
    expect(buildEconomics(i18n.t, DEFAULTS, 'gas', N.none)).toBeNull();
  });

  it('one size line over every kind of pump, a diamond for a theoretical one', () => {
    const base = N.gas_none!;
    const out = buildEconomics(i18n.t, DEFAULTS, 'gas', base)!;
    const [curve] = out.figures.size.data as unknown as Array<{
      name: string;
      x: number[];
      marker: { symbol: string[] };
    }>;
    expect(curve.name).toBe('Best heat pump per size (◆ theoretical)');
    expect(curve.x).toEqual(base.size.sizes.map((s) => s.point.Q_demand));
    expect(curve.marker.symbol).toEqual(
      base.size.sizes.map((s) => (s.point.theoretical ? 'diamond' : 'circle'))
    );
    // Every point on the line can be clicked to analyse that pump.
    expect(out.sizes).toHaveLength(base.size.sizes.length);
  });
});
