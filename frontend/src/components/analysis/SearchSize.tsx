/** How big the heat pump search was: every combination looked at, how many
 *  COPs were computed and how many of those a model predicted, the feasible
 *  points left, and how long it took on the server. Shown at the top of the
 *  heat pump view (HeatPumpView). */

import { useTranslation } from 'react-i18next';
import { useAnalysisStore } from '../../store/analysisStore';

export default function SearchSize() {
  const { t, i18n } = useTranslation();
  const result = useAnalysisStore((s) => s.hpiOptimizationResult);
  const search = result?.diagnostics;
  if (!result || !search?.combinations) return null;

  const count = (v?: number | null) => (v ?? 0).toLocaleString(i18n.language);
  const seconds =
    search.duration_ms != null
      ? (search.duration_ms / 1000).toLocaleString(i18n.language, {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        })
      : null;

  return (
    <p className="pa-search-size">
      {t('optimization.search_size', {
        combinations: count(search.combinations),
        pumps: count(search.heat_pumps),
        pairs: count(search.grid_points),
        evaluations: count(search.cop_evaluations),
        predictions: count(search.cop_predictions),
        feasible: count(result.feasible_points.length),
      })}
      {seconds && ` ${t('optimization.search_time', { seconds })}`}
    </p>
  );
}
