import { describe, it, expect } from 'vitest';
import {
  orphanProcesses,
  reindexPlans,
  removeProcesses,
  removeStreamFromSelection,
  withoutIndex,
} from './processIndex';
import type { ProcessNode } from '../types/process';

const procs = ['a', 'b', 'c', 'd'].map((name) => ({ name }) as ProcessNode);

describe('removeProcesses', () => {
  it('drops the node and shifts later group members and selection keys', () => {
    const next = removeProcesses(
      [1],
      procs,
      [
        [0, 1],
        [2, 3],
      ],
      {
        stream_0_0: true,
        stream_1_0: true,
        stream_2_0: false,
        stream_3_1_0: true,
      }
    );
    expect(next.processes.map((p) => p.name)).toEqual(['a', 'c', 'd']);
    expect(next.groups).toEqual([[0], [1, 2]]);
    expect(next.selection).toEqual({
      stream_0_0: true,
      stream_1_0: false,
      stream_2_1_0: true,
    });
  });

  it('handles a whole group at once', () => {
    const next = removeProcesses([0, 1], procs, [[2, 3]], {});
    expect(next.groups).toEqual([[0, 1]]);
    expect(next.processes.map((p) => p.name)).toEqual(['c', 'd']);
  });
});

describe('orphanProcesses', () => {
  it('finds processes no group claims', () => {
    expect(orphanProcesses(procs, [[0, 2]])).toEqual([1, 3]);
    expect(
      orphanProcesses(procs, [
        [0, 1],
        [2, 3],
      ])
    ).toEqual([]);
  });
});

describe('removeStreamFromSelection', () => {
  it('drops the stream and moves the later ones of its subprocess up', () => {
    const sel = {
      stream_1_0: true,
      stream_1_1: false,
      stream_1_2: true,
      stream_0_2: true,
      stream_1_0_3: true,
    };
    expect(removeStreamFromSelection(sel, 1, 1)).toEqual({
      stream_1_0: true,
      stream_1_1: true,
      stream_0_2: true,
      stream_1_0_3: true,
    });
  });
});

describe('withoutIndex', () => {
  it('closes the deleted process’s diagram and moves later ones up', () => {
    expect(withoutIndex({ 1: true }, 1)).toEqual({});
    expect(withoutIndex({ 2: true }, 0)).toEqual({ 1: true });
    expect(withoutIndex({ 0: true }, 3)).toEqual({ 0: true });
  });
});

describe('reindexPlans', () => {
  const plans = { g0: 'a', g1: 'b', g2: 'c', s0: 'x', s1: 'y', s3: 'z' };

  it('drops a deleted process and its subprocesses and moves the later ones down', () => {
    expect(reindexPlans(plans, 1, [1])).toEqual({ g0: 'a', g1: 'c', s0: 'x', s2: 'z' });
  });

  it('moves subprocess backgrounds past a deleted subprocess', () => {
    expect(reindexPlans(plans, null, [0])).toEqual({ g0: 'a', g1: 'b', g2: 'c', s0: 'y', s2: 'z' });
  });

  it('keeps keys it does not know', () => {
    expect(reindexPlans({ other: 'q' }, 0, [0])).toEqual({ other: 'q' });
  });
});
