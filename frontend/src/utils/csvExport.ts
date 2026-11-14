/**
 * Exports of the project: the stream table and the distance matrix as CSV
 * (made by the backend, POST /api/io/export-csv and /api/io/export-distances,
 * the one format the MCP server and the CSV import use too) and the map as
 * an image (made here: it is a picture of the screen).
 */

import client from '../api/client';
import i18n from '../i18n';
import type { ProjectState } from '../types/project';

async function backendCsv(path: string, state: ProjectState): Promise<string> {
  const { data } = await client.post<string>(path, state, {
    responseType: 'text',
    transformResponse: (d) => d,
  });
  return data;
}

/** The project's streams as CSV text (semicolon separated, quoted). */
export function projectCsv(state: ProjectState): Promise<string> {
  return backendCsv('/api/io/export-csv', state);
}

/** Distances between the subprocesses as CSV text. */
export function distanceCsv(
  state: ProjectState,
  metric: 'manhattan' | 'euclidean'
): Promise<string> {
  return backendCsv(`/api/io/export-distances?metric=${metric}`, state);
}

function downloadCsv(csv: string, filename: string) {
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function download(make: () => Promise<string>, filename: string) {
  try {
    downloadCsv(await make(), filename);
  } catch (err) {
    console.error('CSV export failed:', err);
    alert(i18n.t('stream_table.export_failed'));
  }
}

export function exportProjectToCsv(state: ProjectState) {
  return download(
    () => projectCsv(state),
    `heattransplan_export_${new Date().toISOString().slice(0, 10)}.csv`
  );
}

export function exportDistanceMatrixToCsv(state: ProjectState, metric: 'manhattan' | 'euclidean') {
  return download(
    () => distanceCsv(state, metric),
    `heattransplan_distances_${metric}_${new Date().toISOString().slice(0, 10)}.csv`
  );
}

export async function exportLiveMapSnapshot() {
  const mapEl = document.querySelector('.leaflet-container');
  if (!mapEl) {
    alert(i18n.t('map.not_on_screen'));
    return;
  }
  try {
    // Fix SVGs missing xmlns for html2canvas
    const svgs = mapEl.querySelectorAll('svg');
    svgs.forEach((svg) => {
      if (!svg.getAttribute('xmlns')) {
        svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      }
    });

    // Loaded on first use: 200 kB nobody needs until they export the map.
    const { default: html2canvas } = await import('html2canvas');
    const canvas = await html2canvas(mapEl as HTMLElement, {
      useCORS: true,
      allowTaint: false,
    });
    const imgData = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = imgData;
    a.download = `heattransplan_map_full_${new Date().toISOString().slice(0, 10)}.png`;
    a.click();
  } catch (err) {
    console.error('Error capturing map:', err);
    alert(i18n.t('map.capture_failed'));
  }
}
