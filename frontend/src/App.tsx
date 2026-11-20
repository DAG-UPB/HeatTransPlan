import { Suspense, lazy, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
// The landing page, loaded at once: the method in four steps and the guided tour.
import HomePage from './pages/HomePage';
import ErrorBoundary from './components/ui/ErrorBoundary';
import { loadEconDefaults } from './api/analysis';
import { trackPage } from './api/usage';

// Plotly and Leaflet are ~90% of the bundle. Loading them eagerly meant a
// phone downloaded several megabytes before it could show the landing page;
// split out, they only arrive when the user opens a page that charts or maps.
const DataCollectionPage = lazy(() => import('./pages/DataCollectionPage'));
const PotentialAnalysisPage = lazy(() => import('./pages/PotentialAnalysisPage'));

function App() {
  // The economic analysis' default inputs come from the backend: asked early,
  // so they are there when the page gets to them (it waits otherwise).
  useEffect(() => {
    loadEconDefaults().catch(() => undefined);
  }, []);
  // Which page is open, counted anonymously (api/usage.ts).
  const { pathname } = useLocation();
  useEffect(() => trackPage(pathname), [pathname]);
  return (
    <ErrorBoundary>
      <AppShell>
        <Suspense
          fallback={
            <div className="route-loading">
              <span className="spinner" />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/data-collection" element={<DataCollectionPage />} />
            <Route path="/potential-analysis" element={<PotentialAnalysisPage />} />
            {/* The preview became the home page; old links still land there. */}
            <Route path="/home-preview" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AppShell>
    </ErrorBoundary>
  );
}

export default App;
