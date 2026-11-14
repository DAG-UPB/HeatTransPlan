/** The input form lists exactly the inputs the backend has defaults for. */

import { expect, it } from 'vitest';
import { econDefaults } from '../../test/backendFixtures';
import { FIELDS, FORM_KEYS, REF_TYPES } from './econConfig';

it('has a field for every default the backend serves, and no other', () => {
  const d = econDefaults();
  expect([...FORM_KEYS].sort()).toEqual(Object.keys(d.form).sort());
  expect(FIELDS.map((f) => f[0]).sort()).toEqual([...FORM_KEYS].sort());
  expect(Object.keys(d.presets).sort()).toEqual([...REF_TYPES].sort());
});
