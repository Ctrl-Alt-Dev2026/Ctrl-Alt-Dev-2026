import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  ElementRef,
  inject,
  input,
  isDevMode,
  output,
  untracked,
  viewChild,
} from '@angular/core';
import type { Color, PickingInfo } from '@deck.gl/core';
import { HexagonLayer } from '@deck.gl/aggregation-layers';
import { IconLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { GeoJSONSource, IControl, Map as MlMap, NavigationControl, StyleSpecification } from 'maplibre-gl';
import { dateRo, GRAVITATE, PRECISE } from '../../../core/format/labels';
import { Camera } from '../../../core/models/camera';
import { Accident, Hotspot } from '../../../core/models/contract';
import { StreetFeature, StreetMetric, StreetProps } from '../../../core/models/streets';

// Free, keyless basemap with OSM building heights; DEM tiles only shade the hills
// (true 3D terrain would bury deck.gl columns on Copou/Bucium).
const STYLE_URL = 'https://tiles.openfreemap.org/styles/dark';
const DEM_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const STYLE_TIMEOUT_MS = 10000;

// Used when the basemap can't load (no internet): data layers still render on a plain ground.
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#0b1017' } }],
};

const HOME = { center: [27.585, 47.1595] as [number, number], zoom: 13.1, pitch: 58, bearing: -18 };

// Sequential heat, low → high (matches --heat-1..4 in styles.scss).
const HEAT: Color[] = [
  [255, 224, 138],
  [255, 179, 71],
  [255, 122, 69],
  [232, 65, 75],
];
const INK: Color = [232, 237, 244];
const MUTED: Color = [147, 160, 178];
const ACCENT = '#8fd3ff';
const PULSE = '#e8414b';
const ACCENT_RGB: Color = [143, 211, 255];
const NIGHT: Color = [11, 16, 23];

// Camera glyph, tinted by deck (mask) so the selected camera can take the accent colour.
const CAMERA_ICON = {
  id: 'camera',
  url:
    'data:image/svg+xml;charset=utf-8,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24"><path fill="#fff" d="M3 7.5A1.5 1.5 0 0 1 4.5 6h9A1.5 1.5 0 0 1 15 7.5v1.8l4.2-2.6A1.2 1.2 0 0 1 21 7.7v8.6a1.2 1.2 0 0 1-1.8 1L15 14.7v1.8a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 3 16.5z"/></svg>',
    ),
  width: 64,
  height: 64,
  mask: true,
};

// Columns over locations with measures sink to this share of their height when "Aplică măsurile" runs.
const APPLIED_LEVEL = 0.15;
const PULSE_MS = 2400;
const CLOSE_UP_ZOOM = 15;

// One drawable polyline of a street (a street is a MultiLineString).
interface StreetPath {
  id: string;
  path: [number, number][];
  value: number;
  props: StreetProps;
}

const EARTH_M = 40075016.686;

/**
 * Camera framing for a street: its main stretch (the longest piece plus pieces within 1.5 km of it, so a
 * far-off fragment with the same name doesn't zoom the view out), its centre, its length along its own
 * direction and its spread across it, and the bearing that lays it left to right (the one closer to `bearing`).
 */
function streetView(lines: [number, number][][], bearing: number) {
  const all = lines.flat();
  if (all.length < 2) return null;
  const lat0 = all.reduce((s, p) => s + p[1], 0) / all.length;
  const lon0 = all.reduce((s, p) => s + p[0], 0) / all.length;
  const kx = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const ky = 110540;
  const local = lines.map((line) => line.map(([lon, lat]) => [(lon - lon0) * kx, (lat - lat0) * ky] as const));
  const length = (line: readonly (readonly [number, number])[]) =>
    line.reduce((s, p, i) => (i ? s + Math.hypot(p[0] - line[i - 1][0], p[1] - line[i - 1][1]) : 0), 0);
  const main = local.reduce((a, b) => (length(b) > length(a) ? b : a));
  const xs = main.map((p) => p[0]);
  const ys = main.map((p) => p[1]);
  const [x1, x2, y1, y2] = [Math.min(...xs) - 1500, Math.max(...xs) + 1500, Math.min(...ys) - 1500, Math.max(...ys) + 1500];
  const pts = local.filter((line) => line.some(([x, y]) => x >= x1 && x <= x2 && y >= y1 && y <= y2)).flat();

  // Principal direction of the points (angle from east, counter-clockwise).
  const mx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const my = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  let sxx = 0, syy = 0, sxy = 0;
  for (const [x, y] of pts) {
    sxx += (x - mx) ** 2;
    syy += (y - my) ** 2;
    sxy += (x - mx) * (y - my);
  }
  const theta = 0.5 * Math.atan2(2 * sxy, sxx - syy);
  const [ux, uy] = [Math.cos(theta), Math.sin(theta)];
  const range = (values: number[]) => {
    const sorted = [...values].sort((a, b) => a - b);
    const at = (q: number) => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
    return [at(0.02), at(0.98)] as const;
  };
  const [u1, u2] = range(pts.map(([x, y]) => x * ux + y * uy));
  const [v1, v2] = range(pts.map(([x, y]) => -x * uy + y * ux));
  const [uc, vc] = [(u1 + u2) / 2, (v1 + v2) / 2];
  const [cx, cy] = [uc * ux - vc * uy, uc * uy + vc * ux];

  // Street azimuth (clockwise from north) minus 90° puts it horizontal on screen; pick the nearer of b, b + 180.
  const b = 90 - (theta * 180) / Math.PI - 90;
  const wrap = (a: number) => ((((a + 180) % 360) + 360) % 360) - 180;
  const near = [wrap(b), wrap(b + 180)].sort((p, q) => Math.abs(wrap(p - bearing)) - Math.abs(wrap(q - bearing)))[0];
  return {
    center: [lon0 + cx / kx, lat0 + cy / ky] as [number, number],
    length: Math.max(u2 - u1, 200),
    width: Math.max(v2 - v1, 100),
    bearing: near,
  };
}

/**
 * deck.gl draws the data (hexagon columns, event dots, rank labels) on its own canvas above the map,
 * synced to the camera (interleaved mode clears the MapLibre 5 canvas). deck layers are only rebuilt
 * when data changes, so continuous animation (pulsing rings)
 * therefore lives in native MapLibre circle layers.
 */
@Component({
  selector: 'app-city-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="host" role="application" aria-label="Harta 3D a Iașului cu accidentele raportate"></div>`,
  styles: `
    :host,
    .host {
      display: block;
      width: 100%;
      height: 100%;
    }
  `,
})
export class CityMap {
  readonly accidents = input.required<Accident[]>();
  readonly hotspots = input.required<Hotspot[]>();
  readonly rankOf = input.required<Map<string, number>>();
  readonly selectedId = input<string | null>(null);
  readonly applied = input(false);
  // Pixels the floating panel covers on the right, so fly-to keeps the target visible.
  readonly rightInset = input(0);
  // A point to fly to that isn't a ranked location (e.g. an event just approved in Import).
  readonly flyToPoint = input<[number, number] | null>(null);
  readonly cameras = input<Camera[]>([]);
  readonly selectedCameraId = input<string | null>(null);
  readonly streets = input<StreetFeature[]>([]);
  // Figure per street in the current source; null = not in that source (drawn nowhere).
  readonly streetValue = input<Map<string, number | null>>(new Map());
  readonly streetMetric = input<StreetMetric>('isu');
  readonly selectedStreetId = input<string | null>(null);
  readonly selectStreet = output<string>();

  readonly selectCamera = output<string>();

  readonly select = output<string>();
  readonly basemapFailed = output<void>();

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private map?: MlMap;
  private overlay?: MapboxOverlay;
  private ready = false;
  private frame = 0;
  private level = 1; // 1 = documented heights, APPLIED_LEVEL = measures applied
  private target = 1;
  private closeUp = false;
  private readonly reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor() {
    afterNextRender(() => this.init());

    effect(() => {
      this.accidents();
      this.hotspots();
      this.selectedId();
      this.rankOf();
      this.cameras();
      this.selectedCameraId();
      this.streets();
      this.streetValue();
      this.selectedStreetId();
      untracked(() => this.render());
    });
    effect(() => {
      const id = this.selectedStreetId();
      untracked(() => this.focusStreet(id));
    });
    effect(() => {
      const id = this.selectedId();
      untracked(() => this.focus(id));
    });
    effect(() => {
      const p = this.flyToPoint();
      untracked(() => {
        if (p && this.map && this.ready)
          this.map.flyTo({ center: p, zoom: 16.6, pitch: 62, duration: this.reducedMotion ? 0 : 3200, essential: true });
      });
    });
    effect(() => {
      const id = this.selectedCameraId();
      untracked(() => {
        const c = id ? this.cameras().find((x) => x.id === id) : undefined;
        if (c && this.map && this.ready)
          this.map.flyTo({ center: [c.lon, c.lat], zoom: 16.4, pitch: 60, duration: this.reducedMotion ? 0 : 2800, essential: true });
      });
    });
    effect(() => {
      const on = this.applied();
      untracked(() => {
        this.target = on ? APPLIED_LEVEL : 1;
        if (this.reducedMotion) {
          this.level = this.target;
          this.render();
        }
      });
    });

    inject(DestroyRef).onDestroy(() => {
      cancelAnimationFrame(this.frame);
      this.map?.remove();
    });
  }

  private init(): void {
    const map = new MlMap({
      container: this.host().nativeElement,
      style: STYLE_URL,
      ...HOME,
      maxPitch: 75,
      attributionControl: { compact: true },
    });
    this.map = map;
    // Dev only: lets you inspect the map from the browser console as `safeMap`.
    if (isDevMode()) (globalThis as Record<string, unknown>)['safeMap'] = map;
    map.addControl(new NavigationControl({ visualizePitch: true }), 'bottom-right');

    let styled = false;
    const fallback = () => {
      if (styled) return;
      styled = true;
      map.setStyle(FALLBACK_STYLE);
      this.basemapFailed.emit();
    };
    const timer = setTimeout(fallback, STYLE_TIMEOUT_MS);
    map.on('error', (e) => {
      if (!map.isStyleLoaded()) fallback();
      else if (isDevMode()) console.warn('map:', e.error?.message);
    });

    map.on('style.load', () => {
      clearTimeout(timer);
      styled = true;
      this.customizeBasemap(map);
      this.addHotspotLayers(map);
      if (!this.overlay) {
        this.overlay = new MapboxOverlay({ interleaved: false, layers: [], getTooltip: (info) => this.tooltip(info) });
        map.addControl(this.overlay as unknown as IControl);
      }
      this.ready = true;
      map.on('zoom', () => {
        const near = map.getZoom() >= CLOSE_UP_ZOOM;
        if (near !== this.closeUp) {
          this.closeUp = near;
          this.render();
        }
      });
      this.render();
      const p = this.flyToPoint();
      if (p) map.jumpTo({ center: p, zoom: 16.6, pitch: 62 });
      else if (this.selectedStreetId()) this.focusStreet(this.selectedStreetId());
      else this.focus(this.selectedId());
      this.loop();
    });
  }

  // Night palette on the OpenFreeMap style, OSM buildings extruded to their height, hill shading.
  private customizeBasemap(map: MlMap): void {
    if (!map.getSource('openmaptiles')) return; // fallback style
    const firstLabel = map.getStyle().layers.find((l) => l.type === 'symbol')?.id;
    const set = (layer: string, prop: Parameters<MlMap['setPaintProperty']>[1], value: string) => {
      if (map.getLayer(layer)) map.setPaintProperty(layer, prop, value);
    };
    set('background', 'background-color', '#0b1017');
    set('water', 'fill-color', '#0e2134');
    set('highway_minor', 'line-color', '#253244');
    set('highway_major_inner', 'line-color', '#33445b');
    set('highway_major_casing', 'line-color', '#1a2432');

    map.addSource('dem', { type: 'raster-dem', tiles: [DEM_TILES], encoding: 'terrarium', tileSize: 256, maxzoom: 14 });
    map.addLayer(
      {
        id: 'hillshade',
        type: 'hillshade',
        source: 'dem',
        paint: {
          'hillshade-exaggeration': 0.45,
          'hillshade-shadow-color': '#04070b',
          'hillshade-highlight-color': '#22324a',
          'hillshade-accent-color': '#0b1017',
        },
      },
      map.getLayer('waterway') ? 'waterway' : firstLabel,
    );

    if (map.getLayer('building')) map.removeLayer('building');
    const height = ['coalesce', ['get', 'render_height'], 8];
    map.addLayer(
      {
        id: 'building-3d',
        type: 'fill-extrusion',
        source: 'openmaptiles',
        'source-layer': 'building',
        minzoom: 12.5,
        paint: {
          'fill-extrusion-color': ['interpolate', ['linear'], height, 0, '#1c2636', 40, '#2a3a52', 120, '#3e5373'],
          'fill-extrusion-height': height,
          'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
          'fill-extrusion-opacity': 0.92,
        },
      } as never,
      firstLabel,
    );
  }

  // Ground rings for ranked locations: a pulse on each, an accent ring on the selected one.
  private addHotspotLayers(map: MlMap): void {
    map.addSource('hotspots', { type: 'geojson', data: this.hotspotGeoJson() });
    const ring = (r: number) => ['interpolate', ['exponential', 1.8], ['zoom'], 12, r * 0.6, 18, r * 12];
    map.addLayer({
      id: 'hotspot-pulse',
      type: 'circle',
      source: 'hotspots',
      paint: {
        'circle-pitch-alignment': 'map',
        'circle-radius': ring(28) as never,
        'circle-opacity': 0,
        'circle-stroke-width': 2,
        'circle-stroke-color': PULSE,
        'circle-stroke-opacity': 0.7,
      },
    });
    map.addLayer({
      id: 'hotspot-selected',
      type: 'circle',
      source: 'hotspots',
      filter: ['==', ['get', 'selected'], true],
      paint: {
        'circle-pitch-alignment': 'map',
        'circle-radius': ring(34) as never,
        'circle-opacity': 0,
        'circle-stroke-width': 3,
        'circle-stroke-color': ACCENT,
      },
    });
  }

  private hotspotGeoJson(): GeoJSON.FeatureCollection {
    const selected = this.selectedId();
    return {
      type: 'FeatureCollection',
      features: this.hotspots().map((h) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
        properties: { id: h.id, selected: h.id === selected },
      })),
    };
  }

  private render(): void {
    if (!this.ready || !this.overlay || !this.map) return;
    (this.map.getSource('hotspots') as GeoJSONSource | undefined)?.setData(this.hotspotGeoJson());

    const accidents = this.accidents();
    const hotspots = this.hotspots();
    const precise = accidents.filter((a) => PRECISE.has(a.precizie_loc));
    const approx = accidents.filter((a) => !PRECISE.has(a.precizie_loc));
    const targeted = new Set(hotspots.filter((h) => h.masuri.length > 0).flatMap((h) => h.event_ids));
    const maxEvents = Math.max(3, ...hotspots.map((h) => h.nr_evenimente));
    const level = this.level;
    const weight = (a: Accident) => (targeted.has(a.event_id) ? level : 1);
    const selected = this.selectedId();
    const rankOf = this.rankOf();
    const cameras = this.cameras();
    const selectedCamera = this.selectedCameraId();
    const pos = (a: Accident): [number, number] => [a.lon!, a.lat!];
    // Street level (or one location selected): columns would fill the screen, so each event shows
    // as a dot coloured by severity instead. With the street layer the streets carry the density, and a
    // handful of precisely placed events would only make lone columns: dots there too.
    const focused = selected !== null || this.closeUp || this.streets().length > 0;
    const streetValue = this.streetValue();
    const selectedStreet = this.selectedStreetId();
    const paths: StreetPath[] = this.streets().flatMap((f) => {
      const value = streetValue.get(f.properties.id);
      return value == null ? [] : f.geometry.coordinates.map((path) => ({ id: f.properties.id, path, value, props: f.properties }));
    });
    const maxStreet = Math.max(1, ...paths.map((p) => p.value));
    const streetColor = (p: StreetPath): Color =>
      p.id === selectedStreet ? ACCENT_RGB : HEAT[Math.min(3, Math.floor((p.value / maxStreet) * 3.999))];
    const eventColor = (a: Accident): Color =>
      a.gravitate === 'deces' ? HEAT[3] : a.gravitate === 'grav' ? HEAT[2] : a.gravitate === 'usor' ? HEAT[1] : MUTED;

    this.overlay.setProps({
      layers: [
        // Streets under everything else: the source figure sets colour and width, never a sum of sources.
        new PathLayer<StreetPath>({
          id: 'streets',
          data: paths,
          getPath: (p) => p.path,
          getColor: streetColor,
          getWidth: (p) => (p.id === selectedStreet ? 26 : 8 + 22 * (p.value / maxStreet)),
          widthUnits: 'meters',
          widthMinPixels: 2,
          capRounded: true,
          jointRounded: true,
          opacity: 0.85,
          pickable: true,
          onClick: (info) => {
            if (info.object) this.selectStreet.emit(info.object.id);
          },
          updateTriggers: { getColor: [selectedStreet, maxStreet], getWidth: [selectedStreet, maxStreet] },
        }),
        new HexagonLayer<Accident>({
          id: 'density',
          data: precise,
          getPosition: pos,
          radius: 140,
          coverage: 0.85,
          extruded: true,
          gpuAggregation: false,
          elevationRange: [0, 650],
          elevationDomain: [0, maxEvents],
          colorDomain: [0, maxEvents],
          colorRange: HEAT,
          getElevationWeight: weight,
          getColorWeight: weight,
          elevationAggregation: 'SUM',
          colorAggregation: 'SUM',
          visible: !focused,
          opacity: 0.9,
          material: { ambient: 0.55, diffuse: 0.6, shininess: 24 },
          pickable: true,
          updateTriggers: { getElevationWeight: level, getColorWeight: level },
        }),
        new ScatterplotLayer<Accident>({
          id: 'approx',
          data: approx,
          getPosition: pos,
          getRadius: 45,
          radiusMinPixels: 6,
          filled: false,
          stroked: true,
          getLineColor: MUTED,
          lineWidthMinPixels: 1.5,
          pickable: true,
        }),
        new ScatterplotLayer<Accident>({
          id: 'events',
          data: precise,
          getPosition: pos,
          getRadius: focused ? 7 : 10,
          radiusMinPixels: focused ? 7 : 2.5,
          getFillColor: focused ? eventColor : INK,
          stroked: focused,
          getLineColor: [11, 16, 23],
          lineWidthMinPixels: 2,
          pickable: true,
          updateTriggers: { getFillColor: focused },
        }),
        new TextLayer<Hotspot>({
          id: 'ranks',
          data: hotspots,
          getPosition: (h) => [h.lon, h.lat],
          getText: (h) => String(rankOf.get(h.id) ?? ''),
          getSize: 18,
          fontFamily: 'Archivo, system-ui, sans-serif',
          fontWeight: 700,
          getColor: (h) => (h.id === selected ? [6, 32, 47] : [16, 12, 6]),
          background: true,
          backgroundPadding: [7, 3],
          getBackgroundColor: (h) => (h.id === selected ? [143, 211, 255] : HEAT[2]),
          billboard: true,
          pickable: true,
          onClick: (info) => {
            if (info.object) this.select.emit(info.object.id);
          },
          updateTriggers: { getColor: selected, getBackgroundColor: selected, getText: rankOf },
          parameters: { depthCompare: 'always' },
        }),
        // Cameras stay readable above buildings and columns.
        new ScatterplotLayer<Camera>({
          id: 'camera-base',
          data: cameras,
          getPosition: (c) => [c.lon, c.lat],
          getRadius: 1,
          radiusUnits: 'pixels',
          radiusMinPixels: 15,
          billboard: true,
          getFillColor: NIGHT,
          stroked: true,
          getLineColor: (c) => (c.id === selectedCamera ? ACCENT_RGB : INK),
          lineWidthMinPixels: 1.5,
          pickable: true,
          onClick: (info) => {
            if (info.object) this.selectCamera.emit(info.object.id);
          },
          updateTriggers: { getLineColor: selectedCamera },
          parameters: { depthCompare: 'always' },
        }),
        new IconLayer<Camera>({
          id: 'camera-icon',
          data: cameras,
          getPosition: (c) => [c.lon, c.lat],
          getIcon: () => CAMERA_ICON,
          getSize: 18,
          getColor: (c) => (c.id === selectedCamera ? ACCENT_RGB : INK),
          billboard: true,
          pickable: true,
          onClick: (info) => {
            if (info.object) this.selectCamera.emit(info.object.id);
          },
          updateTriggers: { getColor: selectedCamera },
          parameters: { depthCompare: 'always' },
        }),
      ],
    });
  }

  private tooltip(info: PickingInfo): { text: string; style: Record<string, string> } | null {
    const o = info.object as (Accident & { count?: number; points?: unknown[] }) | undefined;
    if (!o) return null;
    let text: string;
    if (info.layer?.id === 'streets') {
      const p = (o as unknown as StreetPath).props;
      const lines = [p.nume, `${p.isu_evenimente} intervenții ISU (2024–2026)`, `${p.presa_evenimente} relatări în presă (2026)`];
      lines.push(p.pmud_2021 !== null ? `IPJ, PMUD: ${p.pmud_2020} accidente în 2020, ${p.pmud_2021} în 2021` : 'Nu apare în tabelul PMUD');
      text = [...lines, 'Clic pentru detalii'].join('\n');
    } else if (info.layer?.id === 'density') {
      const n = o.count ?? o.points?.length ?? 0;
      text = `${n} ${n === 1 ? 'eveniment localizat precis' : 'evenimente localizate precis'} în această zonă`;
    } else if (info.layer?.id.startsWith('camera')) {
      text = `Cameră: ${(o as unknown as Camera).nume}\nClic pentru imagine`;
    } else if ('event_id' in o) {
      text = `${dateRo(o.data_eveniment)}, ${o.ora ?? 'oră necunoscută'}\n${GRAVITATE[o.gravitate]}: „${o.loc_text}”`;
    } else {
      return null;
    }
    return {
      text,
      style: {
        background: 'rgb(16 23 34 / 0.94)',
        color: '#e8edf4',
        font: '500 0.85rem/1.4 Archivo, system-ui, sans-serif',
        padding: '0.5rem 0.65rem',
        borderRadius: '0.375rem',
        border: '1px solid #263243',
        maxWidth: '18rem',
        whiteSpace: 'pre-line',
      },
    };
  }

  private focus(id: string | null): void {
    if (!this.map || !this.ready) return;
    const h = id ? this.hotspots().find((x) => x.id === id) : undefined;
    const padding = { top: 80, bottom: 90, left: 20, right: this.rightInset() };
    const duration = this.reducedMotion ? 0 : h ? 3200 : 2400;
    if (h) {
      this.map.flyTo({ center: [h.lon, h.lat], zoom: 16.3, pitch: 64, bearing: this.map.getBearing() + 40, padding, duration, essential: true });
    } else if (!this.selectedStreetId()) {
      // Leaving a location for a street must not fly home over the street's own camera move.
      this.map.flyTo({ ...HOME, padding, duration, essential: true });
    }
  }

  // Frames the street's main stretch across the screen: the camera turns so the street runs left to right,
  // which keeps the whole stretch at a similar scale under the pitch.
  private focusStreet(id: string | null): void {
    if (!this.map || !this.ready || !id) return;
    const f = this.streets().find((s) => s.properties.id === id);
    if (!f) return;
    const view = streetView(f.geometry.coordinates, this.map.getBearing());
    if (!view) return;
    const canvas = this.map.getCanvas();
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
    // Wide screens float the title, legend and dock over the map; stacked ones put them outside it.
    const padding = this.rightInset() > 0
      ? { top: 7 * rem, bottom: 9 * rem, left: 3 * rem, right: this.rightInset() + 2 * rem }
      : { top: 2 * rem, bottom: 2 * rem, left: 1.5 * rem, right: 1.5 * rem };
    const width = Math.max(10 * rem, canvas.clientWidth - padding.left - padding.right);
    const height = Math.max(8 * rem, canvas.clientHeight - padding.top - padding.bottom);
    // Metres per pixel needed for the length across, and for the width up the (pitched, so foreshortened) screen.
    const mpp = Math.max((view.length * 1.2) / width, (view.width * 2.2) / height, 1.2);
    const zoom = Math.log2((EARTH_M * Math.cos((view.center[1] * Math.PI) / 180)) / (512 * mpp));
    this.map.flyTo({
      center: view.center,
      zoom: Math.min(16.4, Math.max(12.6, zoom)),
      bearing: view.bearing,
      pitch: 50,
      padding,
      duration: this.reducedMotion ? 0 : 2200,
      essential: true,
    });
  }

  // Pulse through MapLibre paint properties; deck is rebuilt only while columns are moving.
  private loop(): void {
    const map = this.map!;
    const tick = (now: number) => {
      // Keep the map still behind an open camera. Continuous pulse repainting
      // competes with video decoding, frame capture and CPU inference.
      if (this.selectedCameraId() || document.hidden) {
        this.frame = requestAnimationFrame(tick);
        return;
      }
      const phase = (now % PULSE_MS) / PULSE_MS;
      if (map.getLayer('hotspot-pulse')) {
        map.setPaintProperty('hotspot-pulse', 'circle-stroke-opacity', 0.8 * (1 - phase));
        map.setPaintProperty('hotspot-pulse', 'circle-stroke-width', 1 + 3 * (1 - phase));
        const r = 22 + 30 * phase;
        map.setPaintProperty('hotspot-pulse', 'circle-radius', ['interpolate', ['exponential', 1.8], ['zoom'], 12, r * 0.6, 18, r * 12]);
      }
      if (this.level !== this.target) {
        const step = (this.target - this.level) * 0.08;
        this.level = Math.abs(step) < 0.002 ? this.target : this.level + step;
        this.render();
      }
      this.frame = requestAnimationFrame(tick);
    };
    cancelAnimationFrame(this.frame);
    if (!this.reducedMotion) this.frame = requestAnimationFrame(tick);
  }
}
