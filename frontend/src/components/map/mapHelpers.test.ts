import { describe, expect, it } from 'vitest';
import { boxesInSelection } from './mapHelpers';
import type { ProcessNode } from '../../types/process';

// Two processes at the same spot, each with one subprocess there too.
const groups = [[0], [1]];
const coords = { 0: { lat: 48, lon: 11 }, 1: { lat: 48, lon: 11 } };
const processes = [
  { name: 'A1', lat: 48, lon: 11 },
  { name: 'B1', lat: 48, lon: 11 },
] as ProcessNode[];
const everything = () => true;

describe('boxesInSelection', () => {
  it('takes processes and subprocesses on the site map', () => {
    const { idxs, ids } = boxesInSelection(everything, groups, coords, processes, {}, false);
    expect(new Set(idxs)).toEqual(new Set([0, 1]));
    expect(ids).toEqual(['group-0', 'group-1', 'sub-0', 'sub-1']);
  });

  it('takes only the open diagram’s subprocesses while it is open', () => {
    const { idxs, ids } = boxesInSelection(
      everything,
      groups,
      coords,
      processes,
      { 0: true },
      true
    );
    expect(idxs).toEqual([0]);
    expect(ids).toEqual(['sub-0']);
  });
});
