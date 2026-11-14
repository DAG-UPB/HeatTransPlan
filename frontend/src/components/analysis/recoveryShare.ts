/** The pinch figures at the heat recovery share chosen on the slider. The
 *  backend sends the maximum recovery with the pinch result; this only takes
 *  the share of it, the same formula as backend/app/services/pinch_figures.py
 *  at_recovery_share (both tested against tests/fixtures/recovery_share_reference.json). */

import type { PinchResult } from '../../types/analysis';

export interface RecoveryShare {
  /** Heat not recovered: heated in and cooled away on top of the minimums. */
  unrecovered: number;
  hot_utility: number;
  cold_utility: number;
  heat_recovery: number;
}

export function atRecoveryShare(
  pinch: Pick<PinchResult, 'hot_utility' | 'cold_utility' | 'max_heat_recovery'>,
  recoveryPct: number
): RecoveryShare {
  const unrecovered = (1 - recoveryPct / 100) * pinch.max_heat_recovery;
  return {
    unrecovered,
    hot_utility: pinch.hot_utility + unrecovered,
    cold_utility: pinch.cold_utility + unrecovered,
    heat_recovery: pinch.max_heat_recovery - unrecovered,
  };
}
