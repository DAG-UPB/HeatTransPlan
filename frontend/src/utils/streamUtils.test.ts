/** The page reads streams exactly as the backend does: both are held to the
 *  same reference files (backend/tests/test_project_analysis.py and
 *  test_backend_logic.py check the backend side). */

import { describe, expect, it } from 'vitest';
import type { ProcessNode } from '../types/process';
import type { Stream } from '../types/stream';
import { backendExample, backendFixture } from '../test/backendFixtures';
import { extractStreamInfo } from './streamInfo';
import { getStreamInfo, selectedStreams } from './streamUtils';

type InfoCase = { stream: Stream; info: Record<string, number | string | null> };
type SelectionCase = {
  example: string;
  selection: Record<string, boolean>;
  streams: ReturnType<typeof selectedStreams>;
};

const close = (got: unknown, want: unknown) =>
  typeof want === 'number' && typeof got === 'number'
    ? Math.abs(got - want) <= 1e-12 * Math.max(1, Math.abs(want))
    : got === want;

describe('stream values', () => {
  const cases = backendFixture<InfoCase[]>('stream_info_reference.json');

  it.each(cases.map((c) => [c.stream.name ?? '?', c] as const))('%s', (_, c) => {
    const got = getStreamInfo(c.stream) as unknown as Record<string, unknown>;
    for (const [k, want] of Object.entries(c.info)) expect(close(got[k], want), k).toBe(true);
    // The map, the table and the CSV read the same numbers.
    const shown = extractStreamInfo(
      c.stream as unknown as Record<string, unknown>
    ) as unknown as Record<string, unknown>;
    for (const k of ['tin', 'tout', 'mdot', 'cp', 'CP', 'Q'])
      expect(close(shown[k], c.info[k]), k).toBe(true);
    expect(shown.type).toBe(
      c.info.type === null ? null : String(c.info.type).startsWith('Hot') ? 'hot' : 'cold'
    );
  });
});

describe('selected streams', () => {
  const cases = backendFixture<SelectionCase[]>('selected_streams_reference.json');

  it.each(cases.map((c, i) => [`${c.example} #${i}`, c] as const))('%s', (_, c) => {
    const project = backendExample<{ processes: ProcessNode[] }>(c.example);
    expect(selectedStreams(project.processes, c.selection)).toEqual(c.streams);
  });
});
