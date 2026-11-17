import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { MapContainer, Pane } from 'react-leaflet';
import { StreamCirclesOverlay } from './StreamCirclesOverlay';
import { StreamArrowsOverlay } from './StreamArrowsOverlay';
import { SubprocessCanvasOverlay } from './MapControls';
import type { ProcessNode } from '../../types/process';

const EVIL = '<img src=x onerror=alert(1)>';

const processes = [
  {
    name: EVIL,
    lat: 48,
    lon: 11,
    streams: [
      {
        name: EVIL,
        type: 'water', // product streams have no arrows
        stream_values: { Tin: '80', Tout: '20', ṁ: '1', cp: '4.2' },
      },
    ],
  },
] as unknown as ProcessNode[];

const onMap = (children: React.ReactNode) =>
  render(
    <MapContainer center={[48, 11]} zoom={14} style={{ width: 400, height: 300 }}>
      <Pane name="streamBubblesPane">{null}</Pane>
      <Pane name="expandedBubblesPane">{null}</Pane>
      <Pane name="canvasPane">{children}</Pane>
    </MapContainer>
  );

describe('stream overlays on the map', () => {
  it('show a stream name with markup as text in the bubble tooltip', () => {
    const { container } = onMap(
      <StreamCirclesOverlay
        processes={processes}
        groups={[[0]]}
        groupNames={['P']}
        groupCoordinates={{ 0: { lat: 48, lon: 11 } }}
      />
    );
    expect(container.querySelector('.stream-circles-icon')).not.toBeNull();
    expect(container.querySelector('img:not(.leaflet-tile)')).toBeNull();
    expect(container.querySelector('circle title')?.textContent).toContain(EVIL);
  });

  it('show it as text in the arrow tooltip', () => {
    const { container } = onMap(
      <StreamArrowsOverlay
        processes={processes}
        groups={[[0]]}
        subprocessMapExpanded={{ 0: true }}
        childMapExpanded={{}}
      />
    );
    expect(container.querySelector('.stream-arrows-icon')).not.toBeNull();
    expect(container.querySelector('img:not(.leaflet-tile)')).toBeNull();
    expect(container.querySelector('g.stream-arrow title')?.textContent).toContain(EVIL);
  });

  it('draw a diagram background only from an image data URL', () => {
    const bg = (image: string) => {
      const { container, unmount } = onMap(<SubprocessCanvasOverlay active image={image} />);
      const style = container.querySelector('.subprocess-canvas-bg div')?.getAttribute('style');
      unmount();
      return style ?? '';
    };
    expect(bg('javascript:alert(1)')).not.toContain('url(');
    expect(bg("https://example.com/x.png') ; x:url('y")).not.toContain('url(');
    expect(bg('data:image/png;base64,iVBORw0KGgo=')).toContain(
      "url('data:image/png;base64,iVBORw0KGgo=')"
    );
  });
});
