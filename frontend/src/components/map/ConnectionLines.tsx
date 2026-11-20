import React, { useEffect, useState } from 'react';
import { Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { ProcessNode } from '../../types/process';
import type { GroupCoords } from './types';
import { boxHalf, routeConnection } from './connectionRoute';

const LINE = '#64748b';

type Pt = { x: number; y: number };

export function ConnectionLines({
  processes,
  groups,
  groupNames,
  groupCoordinates,
  subprocessMapExpanded,
  childMapExpanded,
}: {
  processes: ProcessNode[];
  groups: number[][];
  groupNames: string[];
  groupCoordinates: Record<string, GroupCoords>;
  subprocessMapExpanded: Record<number, boolean>;
  childMapExpanded: Record<number, boolean>;
  onElementDoubleClick?: (type: 'group' | 'sub' | 'child' | 'stream', id: any, subId?: any) => void;
}) {
  const map = useMap();
  // The lines are laid out in screen pixels, between boxes that keep their
  // pixel size: any change of view lays them out again, or they drift apart.
  const [, setView] = useState(0);
  useEffect(() => {
    const redraw = () => setView((n) => n + 1);
    const events = 'zoomend moveend resize viewreset rotate';
    map.on(events, redraw);
    return () => {
      map.off(events, redraw);
    };
  }, [map]);

  // A screen-space drawing pinned at its top-left corner.
  const pinned = (key: string, at: Pt, w: number, h: number, html: string, onClick?: any) => (
    <Marker
      key={key}
      position={map.containerPointToLatLng(L.point(at.x, at.y))}
      icon={L.divIcon({
        className: 'conn-drawing',
        html,
        iconSize: [w, h],
        iconAnchor: [0, 0],
      })}
      interactive={!!onClick}
      eventHandlers={onClick ? { click: onClick } : undefined}
    />
  );

  const drawConn = (p: ProcessNode, tgt: ProcessNode) => {
    const srcLat = parseFloat(String(p.lat));
    const srcLon = parseFloat(String(p.lon));
    const tLat = parseFloat(String(tgt.lat));
    const tLon = parseFloat(String(tgt.lon));
    if (isNaN(srcLat) || isNaN(srcLon) || isNaN(tLat) || isNaN(tLon)) return null;

    const p1 = map.latLngToContainerPoint([srcLat, srcLon]);
    const p2 = map.latLngToContainerPoint([tLat, tLon]);
    const src = boxHalf(p.name, p.box_scale);
    const dst = boxHalf(tgt.name, tgt.box_scale);
    // Edge to edge, so no part of the line hides under a box.
    const route = routeConnection(p1, p2, src, dst);
    if (!route) return null;

    // Line and arrowhead in one drawing: the tip touches the target box.
    const rad = (route.angle * Math.PI) / 180;
    const d = { x: Math.cos(rad), y: Math.sin(rad) };
    const tip = { x: route.arrow.x + d.x * 10, y: route.arrow.y + d.y * 10 };
    const base = { x: route.arrow.x - d.x * 2, y: route.arrow.y - d.y * 2 };
    const wing = { x: -d.y * 6, y: d.x * 6 };
    const path = [route.start, route.mid1, route.mid2, base];
    const head = [
      tip,
      { x: base.x + wing.x, y: base.y + wing.y },
      { x: base.x - wing.x, y: base.y - wing.y },
    ];
    const all = [...path, ...head];
    const o = {
      x: Math.min(...all.map((q) => q.x)) - 4,
      y: Math.min(...all.map((q) => q.y)) - 4,
    };
    const w = Math.max(...all.map((q) => q.x)) - o.x + 4;
    const h = Math.max(...all.map((q) => q.y)) - o.y + 4;
    const pts = (qs: Pt[]) =>
      qs.map((q) => `${(q.x - o.x).toFixed(1)},${(q.y - o.y).toFixed(1)}`).join(' ');
    const key = `conn-${p.name}-${tgt.name}`;
    const line = pinned(
      key,
      o,
      w,
      h,
      `<svg width="${w}" height="${h}" style="display:block;overflow:visible">` +
        `<polyline points="${pts(path)}" fill="none" stroke="${LINE}" stroke-width="2" stroke-linejoin="round" />` +
        `<polygon points="${pts(head)}" fill="${LINE}" /></svg>`
    );

    return line;
  };

  const connections: React.ReactElement[] = [];
  const targetsOf = (p: ProcessNode) =>
    (p.next || '')
      .split(',')
      .map((n) => n.trim())
      .filter(Boolean);

  const expandedGroups = groups.map((_, g) => g).filter((g) => subprocessMapExpanded[g]);

  // 1. Between processes, when no process is opened.
  if (expandedGroups.length === 0) {
    const seen = new Set<string>();
    groups.forEach((subIdxs, gIdx) => {
      subIdxs.forEach((si) => {
        targetsOf(processes[si]).forEach((tName) => {
          const tg = groups.findIndex((t) => t.some((tsi) => processes[tsi].name === tName));
          const pair = `${gIdx}-${tg}`;
          if (tg === -1 || tg === gIdx || seen.has(pair)) return;
          seen.add(pair);
          const a = groupCoordinates[gIdx];
          const b = groupCoordinates[tg];
          if (!a || !b) return;
          const node = (g: number, c: GroupCoords) =>
            ({
              name: groupNames[g] || `Process ${g + 1}`,
              lat: c.lat,
              lon: c.lon,
              box_scale: c.box_scale || 1.5,
            }) as ProcessNode;
          const el = drawConn(node(gIdx, a), node(tg, b));
          if (el) connections.push(el);
        });
      });
    });
  }

  // 2. Between the subprocesses of an opened process (those not opened themselves).
  expandedGroups.forEach((g) => {
    const visible = groups[g].filter((si) => !childMapExpanded[si]);
    visible.forEach((si) => {
      targetsOf(processes[si]).forEach((tName) => {
        const ti = visible.find((idx) => processes[idx].name === tName);
        if (ti === undefined) return;
        const el = drawConn(processes[si], processes[ti]);
        if (el) connections.push(el);
      });
    });
  });

  // 3. Between the children of an opened subprocess.
  expandedGroups.forEach((g) => {
    groups[g].forEach((si) => {
      if (!childMapExpanded[si]) return;
      const children = processes[si].children || [];
      children.forEach((c) => {
        targetsOf(c).forEach((tName) => {
          const tgt = children.find((pp) => pp.name === tName);
          const el = tgt && drawConn(c, tgt);
          if (el) connections.push(el);
        });
      });
    });
  });

  return <>{connections}</>;
}
