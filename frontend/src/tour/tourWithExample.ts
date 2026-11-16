/** Start the guided tour on the example plant. The tour shows the example, but
 *  never replaces someone's own project without asking; declining tours their
 *  own project instead. Used by the home page and the header's "?" there. */

import type { TFunction } from 'i18next';
import type { NavigateFunction } from 'react-router-dom';
import { getExample } from '../api/io';
import { useProjectStore } from '../store/projectStore';
import { loadProject } from '../store/loadProject';
import { startTour } from './guidedTour';

export const EXAMPLE = 'heat_integration_example_1.json';

export const hasOwnData = () => (useProjectStore.getState().state.processes?.length ?? 0) > 0;

/** Loads the example project; throws if it cannot be fetched. */
export async function loadExampleProject() {
  loadProject(await getExample(EXAMPLE));
}

/** Throws if the example cannot be loaded; the tour then does not start. */
export async function tourWithExample(navigate: NavigateFunction, t: TFunction, from = 0) {
  if (!hasOwnData() || window.confirm(t('home_preview.tour_replace'))) {
    await loadExampleProject();
  }
  startTour(navigate, t, from);
}
