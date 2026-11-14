/** The slider's share of heat recovery: the same answers as the backend's
 *  at_recovery_share (backend/tests/test_backend_logic.py reads this fixture too). */

import { expect, it } from 'vitest';
import { backendFixture } from '../../test/backendFixtures';
import { atRecoveryShare, type RecoveryShare } from './recoveryShare';

type Row = {
  example: string;
  t_min: number;
  recovery_pct: number;
  pinch: { hot_utility: number; cold_utility: number; max_heat_recovery: number };
  expected: RecoveryShare;
};

const rows = backendFixture<Row[]>('recovery_share_reference.json');

it('gives the backend figures at every share', () => {
  expect(rows.length).toBeGreaterThan(100);
  for (const r of rows) expect(atRecoveryShare(r.pinch, r.recovery_pct)).toEqual(r.expected);
});
