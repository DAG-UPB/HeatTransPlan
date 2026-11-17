/** Guards for asking a Leaflet map where something is once it is gone.
 *
 *  Leaflet keeps a pane's position on the element itself (`_leaflet_pos`).
 *  When the map is removed (leaving the page, switching the mobile pane) it
 *  deletes its panes, but a tooltip or popup updated by leaflet-rotate, or a
 *  marker or line redrawn in the same tick, may still ask for a position.
 *  That read `undefined._leaflet_pos`, and the error screen took over the
 *  whole app ("Cannot read properties of undefined (reading '_leaflet_pos')").
 *  A map or element that is gone has nothing to show, so it answers (0, 0).
 *
 *  Import once, after leaflet and leaflet-rotate (MapViewer does). */

import L from 'leaflet';

type MapInternals = { _mapPane?: HTMLElement; _getMapPanePos(): L.Point };

const mapProto = L.Map.prototype as unknown as MapInternals;
const mapPanePos = mapProto._getMapPanePos;
mapProto._getMapPanePos = function (this: MapInternals) {
  return this._mapPane ? mapPanePos.call(this) : L.point(0, 0);
};

// leaflet-rotate reads popup, tooltip and marker positions through
// L.DomUtil.getPosition, also for elements not (or no longer) on the map.
const getPosition = L.DomUtil.getPosition;
L.DomUtil.getPosition = (el: HTMLElement) => (el ? getPosition(el) : L.point(0, 0));
