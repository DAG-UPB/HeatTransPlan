/** Load a whole case (a saved file, an example, or one an AI loads) in place
 *  of what the page holds. The scenarios of the previous case go with it:
 *  they describe streams that are no longer there. null starts an empty one. */

import type { ProjectState } from '../types/project';
import { isSafeImageUrl } from '../utils/safeHtml';
import { useAnalysisStore } from './analysisStore';
import { useProjectStore } from './projectStore';
import { useUIStore } from './uiStore';

/** The case without plan images we would not draw: a file or an AI command
 *  can carry any text there, and it ends up in the map's HTML. */
export function withSafePlans(state: ProjectState): ProjectState {
  const plans = Object.entries(state.canvas_plans ?? {}).filter(([, url]) => isSafeImageUrl(url));
  return {
    ...state,
    site_plan: state.site_plan && isSafeImageUrl(state.site_plan.url) ? state.site_plan : null,
    ...(state.canvas_plans ? { canvas_plans: Object.fromEntries(plans) } : {}),
  };
}

export function loadProject(state: ProjectState | null) {
  const project = useProjectStore.getState();
  if (state) project.setState(withSafePlans(state));
  else project.resetState();
  useAnalysisStore.getState().resetScenarios();
  // Open the first process and its first subprocess, so data collection shows
  // its streams straight away. Also clears what was open in the previous case.
  const first = state?.proc_groups?.[0]?.[0];
  useUIStore.setState({
    expandedGroups: new Set(first === undefined ? [] : [0]),
    expandedSubprocesses: new Set(first === undefined ? [] : [first]),
    activeSections: {},
  });
}
