import { describe, expect, it } from 'vitest';
import { escapeHtml, isSafeImageUrl, safeImageUrl } from './safeHtml';
import { createDivIcon } from '../components/map/mapHelpers';
import { streamSvgText } from './streamInfo';
import { withSafePlans } from '../store/loadProject';
import { projectStateSchema } from '../schemas/projectSchema';
import type { ProjectState } from '../types/project';

const EVIL = '<img src=x onerror=alert(1)>';
const PNG =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==';

// What Leaflet does with a divIcon's html.
const render = (html: string) => {
  const div = document.createElement('div');
  div.innerHTML = html;
  return div;
};

describe('escapeHtml', () => {
  it('escapes markup and quotes', () => {
    expect(escapeHtml(`${EVIL}"'&`)).toBe('&lt;img src=x onerror=alert(1)&gt;&quot;&#39;&amp;');
    expect(escapeHtml(null)).toBe('');
    expect(escapeHtml(42)).toBe('42');
  });
});

describe('map labels', () => {
  it('shows a process name with markup as text', () => {
    const icon = createDivIcon('', EVIL, '', 1, true, false, `g"${EVIL}`, `1" onclick="x`);
    const div = render(String(icon.options.html));
    expect(div.querySelector('img')).toBeNull();
    expect(div.textContent?.trim()).toBe(EVIL);
    const marker = div.querySelector('.draggable-marker')!;
    expect(marker.getAttribute('data-marker-id')).toBe('1" onclick="x');
    expect(marker.getAttribute('onclick')).toBeNull();
  });

  it('escapes stream values in the SVG labels', () => {
    const text = streamSvgText({ tin: EVIL as unknown as number, tout: null, mdot: 1, cp: null });
    expect(render(`<svg><text>${text.tin}</text></svg>`).querySelector('img')).toBeNull();
    expect(text.tout).toBe('');
  });
});

describe('plan images', () => {
  it('accepts only image data URLs and object URLs', () => {
    expect(isSafeImageUrl(PNG)).toBe(true);
    expect(isSafeImageUrl('data:image/jpeg;base64,/9j/4AAQ')).toBe(true);
    expect(isSafeImageUrl('blob:http://localhost:5173/0b3c6a1e-2f4d-4c5e-9a8b-1234567890ab')).toBe(
      true
    );
    for (const bad of [
      'javascript:alert(1)',
      'https://example.com/plan.png',
      'data:image/svg+xml;base64,PHN2Zz4=',
      "data:image/png;base64,AAAA') ; background:url('https://example.com/x",
      'data:text/html;base64,PHNjcmlwdD4=',
      42,
      null,
    ]) {
      expect(isSafeImageUrl(bad)).toBe(false);
      expect(safeImageUrl(bad)).toBeUndefined();
    }
  });

  it('drops unsafe plans when a case is loaded', () => {
    const state = {
      processes: [],
      proc_groups: [],
      proc_group_names: [],
      proc_group_coordinates: {},
      site_plan: {
        url: 'javascript:alert(1)',
        bounds: [
          [0, 0],
          [1, 1],
        ],
      },
      canvas_plans: { g0: PNG, g1: 'https://example.com/plan.png' },
    } as ProjectState;
    const safe = withSafePlans(state);
    expect(safe.site_plan).toBeNull();
    expect(safe.canvas_plans).toEqual({ g0: PNG });
    const good = withSafePlans({
      ...state,
      site_plan: {
        url: PNG,
        bounds: [
          [0, 0],
          [1, 1],
        ],
      },
    });
    expect(good.site_plan?.url).toBe(PNG);
  });

  it('refuses a project file with a plan that is not an image', () => {
    const base = {
      processes: [],
      proc_groups: [],
      proc_group_names: [],
      proc_group_coordinates: {},
    };
    const plan = (url: string) => ({
      url,
      bounds: [
        [0, 0],
        [1, 1],
      ],
    });
    expect(projectStateSchema.safeParse({ ...base, site_plan: plan(PNG) }).success).toBe(true);
    expect(
      projectStateSchema.safeParse({ ...base, site_plan: plan('javascript:alert(1)') }).success
    ).toBe(false);
    expect(
      projectStateSchema.safeParse({ ...base, canvas_plans: { g0: 'https://example.com/x.png' } })
        .success
    ).toBe(false);
  });
});
