/** The "?" in the header, beside the theme switch: tours the open page's own
 *  steps. On a page without steps of its own (home) it starts the whole tour. */

import { CircleHelp } from 'lucide-react';
import { track } from '../../api/usage';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { pageSteps, startTour } from '../../tour/guidedTour';
import { tourWithExample } from '../../tour/tourWithExample';

export default function PageTourButton() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { from, to } = pageSteps(useLocation().pathname);
  const label = from < 0 ? t('home_preview.start_tour') : t('tour.page_help');
  const onClick = () => {
    track('ui:page_tour');
    if (from >= 0) return startTour(navigate, t, from, to);
    tourWithExample(navigate, t).catch((e: unknown) =>
      window.alert(e instanceof Error ? e.message : String(e))
    );
  };
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onClick}
      data-tip={label}
      aria-label={label}
    >
      <CircleHelp size={16} />
    </button>
  );
}
