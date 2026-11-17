/** The AI's commands change the page exactly as its controls do. */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAnalysisStore } from '../store/analysisStore';
import { useProjectStore } from '../store/projectStore';
import type { HPIOptimizationResult } from '../types/analysis';
import type { ProjectState } from '../types/project';
import fixture from '../test/fixtures/optimization.json';
import {
  asksFor,
  runAiCommand,
  runCommand,
  setConfirmer,
  useAiHistory,
  type AskLine,
} from './commands';
import { econDefaults } from '../test/backendFixtures';

// The CSV comes from the backend; here a stand-in that says what it was sent.
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(async (url: string, state: ProjectState) => ({
      data: [`${url}`, ...state.processes.map((p) => p.name)].join('\n'),
    })),
  },
}));

// The backend's example project. A glob, not an import: the frontend image is
// built from frontend/ alone, where the type check cannot see backend/.
const example = Object.values(
  import.meta.glob('../../../backend/app/data/examples/heat_integration_example_1.json', {
    eager: true,
    import: 'default',
  })
)[0];
const opt = fixture.optimization as unknown as HPIOptimizationResult;

beforeEach(() => {
  useProjectStore.getState().setState(example as unknown as ProjectState);
  useAnalysisStore.setState({
    selectedStreams: {},
    tMin: 10,
    hpiOptimizationResult: opt,
    selectedHPPoints: [],
    pinchLoading: false,
    hpiLoading: false,
    hpiOptimizationLoading: false,
    scenarios: [],
    activeScenarioId: null,
    // As loaded from the backend at start.
    econDefaults: econDefaults(),
    econForm: econDefaults().form,
    econRefType: 'gas',
  });
  useAiHistory.setState({ steps: [] });
});

/** A saved scenario, as the page keeps one. */
const scenario = () => useAnalysisStore.getState().saveScenario('Kept');

describe('live commands', () => {
  it('selects streams like the stream table', async () => {
    const r = (await runCommand('select_streams', { all: true })) as { selected: string[] };
    expect(r.selected).toHaveLength(6);
    await runCommand('select_streams', { keys: ['stream_0_0'], value: false });
    expect(useAnalysisStore.getState().selectedStreams.stream_0_0).toBe(false);
    expect(useProjectStore.getState().state.selected_streams?.stream_0_0).toBe(false);
    await expect(runCommand('select_streams', { keys: ['stream_9_9'] })).rejects.toThrow(
      /Unknown stream/
    );
  });

  it('selects by process and by subprocess, and never ticks streams nobody named', async () => {
    useAnalysisStore.setState({ selectedStreams: { stream_0_0: true } });
    const one = (await runCommand('select_streams', { keys: ['stream_2_1'] })) as {
      selected: string[];
    };
    expect(one.selected).toEqual(['stream_0_0', 'stream_2_1']);
    const sub = (await runCommand('select_streams', { none: true, subprocess: 2 })) as {
      selected: string[];
    };
    expect(sub.selected).toEqual(['stream_2_0', 'stream_2_1']);
    const all = (await runCommand('select_streams', { process: 0 })) as { selected: string[] };
    expect(all.selected).toHaveLength(6);
    await expect(runCommand('select_streams', { process: 3 })).rejects.toThrow(
      /no process 3; there are 1/
    );
    await expect(runCommand('select_streams', { keys: 'stream_0_0' })).rejects.toThrow(/list/);
    await expect(runCommand('select_streams', {})).rejects.toThrow(/Say which/);
  });

  it('applies a single step without touching scenarios, and takes it back', async () => {
    scenario();
    const before = useProjectStore.getState().state;
    const names = [...before.proc_group_names, 'Dryer'];
    await runCommand('edit_project', { changes: { proc_group_names: names }, label: 'add Dryer' });
    expect(useProjectStore.getState().state.proc_group_names).toEqual(names);
    expect(useProjectStore.getState().state.processes).toBe(before.processes);
    expect(useAnalysisStore.getState().scenarios.map((s) => s.name)).toEqual(['Kept']);
    await expect(runCommand('edit_project', { changes: { map_center: [0, 0] } })).rejects.toThrow(
      /cannot change map_center/
    );
    expect(await runCommand('undo', {})).toEqual({ undone: 'add Dryer', steps_left: 0 });
    expect(useProjectStore.getState().state.proc_group_names).toEqual(before.proc_group_names);
    await expect(runCommand('undo', {})).rejects.toThrow(/no step/);
  });

  it('loads a whole case in place of the old one, scenarios included', async () => {
    scenario();
    await runCommand('edit_project', { changes: { proc_group_names: ['X'] } });
    const r = await runCommand('set_project', {});
    expect(r).toEqual({ processes: 0, streams: 0 });
    expect(useAnalysisStore.getState().scenarios).toEqual([]);
    expect(useAiHistory.getState().steps).toEqual([]);
  });

  it('sets ΔTmin and the heat recovery share', async () => {
    await runCommand('set_t_min', { value: 15 });
    expect(useAnalysisStore.getState().tMin).toBe(15);
    await runCommand('set_recovery_pct', { value: 140 });
    expect(useAnalysisStore.getState().recoveryPct).toBe(100);
    await expect(runCommand('set_t_min', { value: 'x' })).rejects.toThrow(/number/);
  });

  it('picks heat pumps by refrigerant and sink temperature', async () => {
    const p = opt.feasible_points.find((x) => !x.theoretical)!;
    await runCommand('select_heat_pumps', {
      points: [{ refrigerant: p.refrigerant, T_sink: p.T_sink }],
    });
    expect(useAnalysisStore.getState().selectedHPPoints).toEqual([p]);
    await runCommand('select_heat_pumps', { clear: true });
    expect(useAnalysisStore.getState().selectedHPPoints).toEqual([]);
  });

  it('changes economics inputs and rejects unknown ones', async () => {
    await runCommand('set_economics', { form: { pFuel: 9 }, ref_type: 'oil' });
    expect(useAnalysisStore.getState().econForm?.pFuel).toBe(9);
    // The oil heater's own values came with it, from the backend's presets.
    expect(useAnalysisStore.getState().econForm?.eta).toBe(econDefaults().presets.oil.eta);
    expect(useAnalysisStore.getState().econRefType).toBe('oil');
    await expect(runCommand('set_economics', { form: { nope: 1 } })).rejects.toThrow(/Unknown/);
    await runCommand('reset_economics', {});
    expect(useAnalysisStore.getState().econForm).toEqual(econDefaults().form);
    expect(useAnalysisStore.getState().econRefType).toBe('gas');
  });

  it('reports the view, waits for quiet and explains unknown commands', async () => {
    const view = (await runCommand('wait_idle', { timeout: 2 })) as { analysis: { t_min: number } };
    expect(view.analysis.t_min).toBe(10);
    await expect(runCommand('fly', {})).rejects.toThrow(/not available here/);
    expect(await runCommand('list_commands', {})).toContain('select_streams');
  });

  it('exports the project as CSV text, made by the backend', async () => {
    const csv = (await runCommand('export_csv', {})) as string;
    expect(csv.split('\n')[0]).toBe('/api/io/export-csv');
    expect(csv.split('\n').length).toBe(1 + useProjectStore.getState().state.processes.length);
    const dist = (await runCommand('export_distances_csv', { metric: 'euclidean' })) as string;
    expect(dist.split('\n')[0]).toBe('/api/io/export-distances?metric=euclidean');
  });
});

describe('the page asks before an AI deletes or replaces', () => {
  /** The user's answers, and what they were asked. */
  const asked: AskLine[][] = [];
  const answer = (allowed: boolean) =>
    setConfirmer(async (lines) => {
      asked.push(lines);
      return allowed;
    });
  beforeEach(() => {
    asked.length = 0;
    setConfirmer(null);
  });

  it('wipes nothing without the user, whoever sends it', async () => {
    const before = useProjectStore.getState().state;
    // No dialog on the page (not connected): refused.
    await expect(runAiCommand('set_project', { state: null })).rejects.toThrow(/declined/);
    answer(false);
    await expect(runAiCommand('set_project', { state: null })).rejects.toThrow(/declined/);
    expect(asked[0]).toEqual([{ kind: 'set_project_empty', name: '' }]);
    expect(useProjectStore.getState().state).toBe(before);
    answer(true);
    expect(await runAiCommand('set_project', { state: null })).toEqual({
      processes: 0,
      streams: 0,
    });
  });

  it('works out itself what a step deletes, by name', async () => {
    const s = useProjectStore.getState().state;
    const gone = s.processes[0].streams?.[0]?.name;
    const processes = s.processes.map((p, i) =>
      i === 0 ? { ...p, streams: (p.streams ?? []).slice(1) } : p
    );
    answer(false);
    await expect(
      runAiCommand('edit_project', { changes: { processes }, label: 'harmless rename' })
    ).rejects.toThrow(/declined/);
    expect(asked[0]).toEqual([{ kind: 'delete_stream', name: gone }]);
    expect(useProjectStore.getState().state.processes).toBe(s.processes);

    const groups = asksFor('edit_project', { changes: { proc_group_names: [], proc_groups: [] } });
    expect(groups).toEqual(s.proc_group_names.map((name) => ({ kind: 'delete_process', name })));
    // Garbage in place of the processes is a deletion too.
    expect(asksFor('edit_project', { changes: { processes: 'x' } })[0].kind).toBe(
      'delete_subprocess'
    );
  });

  it('asks about plans and scenarios, and lets plain steps through', async () => {
    useProjectStore.getState().setState({
      ...useProjectStore.getState().state,
      site_plan: {
        url: 'data:a',
        bounds: [
          [0, 0],
          [1, 1],
        ],
      } as never,
      canvas_plans: { g0: 'data:b' },
    });
    const name = useProjectStore.getState().state.proc_group_names[0];
    expect(asksFor('remove_site_plan', {})).toEqual([{ kind: 'remove_site_plan', name: '' }]);
    expect(
      asksFor('edit_project', { changes: { site_plan: { url: 'data:c', bounds: [] } } })
    ).toEqual([{ kind: 'replace_site_plan', name: '' }]);
    expect(asksFor('remove_subprocess_plan', { key: 'g0' })).toEqual([
      { kind: 'remove_subprocess_plan_named', name },
    ]);
    expect(asksFor('edit_project', { changes: { canvas_plans: {} } })).toEqual([
      { kind: 'remove_subprocess_plan_named', name },
    ]);
    scenario();
    expect(asksFor('delete_scenario', { index: 0 })).toEqual([
      { kind: 'delete_scenario_named', name: 'Kept' },
    ]);
    // The sender may name the file; the question is still about replacing all.
    expect(
      asksFor('set_project', { state: {}, ask: { kind: 'import_csv', name: 'x.csv' } })
    ).toEqual([{ kind: 'import_csv', name: 'x.csv' }]);
    expect(
      asksFor('set_project', { state: {}, ask: { kind: 'delete_stream', name: 'x' } })
    ).toEqual([{ kind: 'set_project', name: '' }]);
    // Adding and changing need no question.
    const names = [...useProjectStore.getState().state.proc_group_names, 'Dryer'];
    expect(asksFor('edit_project', { changes: { proc_group_names: names } })).toEqual([]);
    await runAiCommand('edit_project', { changes: { proc_group_names: names } });
    expect(asked).toEqual([]);
  });
});
