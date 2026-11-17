/** Plotly with only the trace types the app draws: scatter (in the core), bar
 *  and heatmap. The full bundle carries maps, 3-D and WebGL besides, several
 *  megabytes nobody uses. A chart with another trace type registers it here.
 *
 *  Every chart follows the width of its own box, not only the window: Plotly's
 *  `responsive` reacts to window resizes alone, so a box that changed width
 *  for another reason (a panel opening, a scrollbar, two columns becoming
 *  one) left the chart at its old size, over its neighbours. */

import { useEffect, useState } from 'react';
import type { PlotProps } from 'react-plotly.js';
import Plotly from 'plotly.js/lib/core';
import bar from 'plotly.js/lib/bar';
import heatmap from 'plotly.js/lib/heatmap';
import createPlotlyComponent from 'react-plotly.js/factory';

Plotly.register([bar, heatmap]);

const PlotlyChart = createPlotlyComponent(Plotly);

export default function Plot(props: PlotProps) {
  // The graph div, known once Plotly drew the chart the first time.
  const [el, setEl] = useState<HTMLElement | null>(null);
  const { onInitialized } = props;

  useEffect(() => {
    if (!el || typeof ResizeObserver === 'undefined') return;
    let frame = 0;
    let width = el.clientWidth;
    const observer = new ResizeObserver(() => {
      // Only a new width counts: the chart's own redraw changes the height.
      if (el.clientWidth === width) return;
      width = el.clientWidth;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        // Not before Plotly has drawn it, nor after it was removed.
        if (el.isConnected && '_fullLayout' in el) void Plotly.Plots.resize(el).catch(() => {});
      });
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [el]);

  return (
    <PlotlyChart
      {...props}
      onInitialized={(figure, div) => {
        setEl(div);
        onInitialized?.(figure, div);
      }}
    />
  );
}
