/** The backend's test fixtures the frontend is held to (backend/tests/fixtures).
 *  Globs, not imports: the frontend image is built from frontend/ alone, where
 *  the type check cannot see backend/. */

import type { EconDefaults } from '../components/analysis/econConfig';

const files = import.meta.glob('../../../backend/tests/fixtures/*.json', {
  eager: true,
  import: 'default',
});

export function backendFixture<T>(name: string): T {
  const hit = Object.entries(files).find(([path]) => path.endsWith(`/${name}`));
  if (!hit) throw new Error(`backend fixture ${name} not found`);
  return hit[1] as T;
}

const examples = import.meta.glob('../../../backend/app/data/examples/*.json', {
  eager: true,
  import: 'default',
});

/** One of the backend's example projects, by file name. */
export function backendExample<T>(name: string): T {
  const hit = Object.entries(examples).find(([path]) => path.endsWith(`/${name}`));
  if (!hit) throw new Error(`backend example ${name} not found`);
  return hit[1] as T;
}

/** What GET /api/analysis/economics/defaults serves (the year is next year). */
export function econDefaults(): EconDefaults {
  const ref = backendFixture<{
    form: Omit<EconDefaults['form'], 'year'>;
    presets: EconDefaults['presets'];
  }>('economics_defaults.json');
  return { form: { ...ref.form, year: new Date().getFullYear() + 1 }, presets: ref.presets };
}
