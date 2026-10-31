// Publish step: turn H3 cells (with deltas) into a map-ready GeoJSON layer and a
// freshness sidecar, and mirror both into the site's public/ dir so the browser
// can fetch them.
//
// Includes Audit Packet P3 / F10 correction: rejects impossible future refresh
// timestamps and respects source-specific cadence thresholds.

import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { cellToBoundary } from 'h3-js';

const DAY_MS = 86400000;

/** Parse a Date | number(ms) | ISO string to epoch ms, or null. */
function toMs(value) {
  if (value === undefined || value === null || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value.getTime();
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/** Round to one decimal place. */
function round1(n) {
  return Math.round(n * 10) / 10;
}

function closeRing(coords) {
  if (!Array.isArray(coords) || coords.length === 0) return [];
  const first = coords[0];
  const last = coords[coords.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) {
    return coords.map((c) => [c[0], c[1]]);
  }
  return [...coords.map((c) => [c[0], c[1]]), [first[0], first[1]]];
}

export function toGeoJSON(cellsWithDeltas) {
  const features = (Array.isArray(cellsWithDeltas) ? cellsWithDeltas : []).map((c) => ({
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [closeRing(cellToBoundary(c.h3, true))],
    },
    properties: {
      h3: c.h3,
      count: c.count ?? 0,
      prior_count: c.prior_count ?? 0,
      delta: c.delta ?? 0,
      delta_pct: c.delta_pct ?? null,
      last_activity: c.last_activity ?? null,
      scope_label: c.scope_label ?? null,
    },
  }));
  return { type: 'FeatureCollection', features };
}

/**
 * Freshness state machine (Fixes F10).
 *
 * Rejects future refresh timestamps (`days < 0`) as 'INVALID_FUTURE_TIMESTAMP'
 * and enforces cadence-specific windows when `cadence === 'daily'`.
 */
export function computeFreshness({ state, lastSuccessAt, cadence, now } = {}) {
  if (state === 'BLOCKED') return 'BLOCKED';

  const last = toMs(lastSuccessAt);
  if (last === null) return 'NEVER_LOADED';

  const nowMs = toMs(now) ?? Date.now();
  const days = (nowMs - last) / DAY_MS;

  // Fix F10: Reject impossible future timestamps
  if (days < 0) return 'INVALID_FUTURE_TIMESTAMP';

  if (cadence === 'daily') {
    if (days <= 1.5) return 'FRESH';
    if (days <= 3.0) return 'AGING';
    return 'STALE';
  }

  if (days <= 7) return 'FRESH';
  if (days <= 14) return 'AGING';
  return 'STALE';
}

export async function publish({
  cells,
  registry,
  state,
  lastSuccessAt,
  baseDir,
  publicDir,
  now,
  stats,
} = {}) {
  if (!registry || !registry.id) throw new Error('publish requires a registry with an id');
  if (!baseDir || !publicDir) throw new Error('publish requires { baseDir, publicDir }');

  const id = registry.id;
  const cellList = Array.isArray(cells) ? cells : [];
  const nowMs = toMs(now) ?? Date.now();
  const lastMs = toMs(lastSuccessAt);

  const geojson = toGeoJSON(cellList);
  const freshness = computeFreshness({
    state,
    lastSuccessAt,
    cadence: registry.cadence,
    now: nowMs,
  });

  const nonPlaceable = stats?.non_placeable ?? 0;
  const recordCount = stats?.output ?? cellList.reduce((sum, c) => sum + (c.count || 0), 0);

  const freshnessDoc = {
    source_id: id,
    title: registry.title ?? null,
    publisher: registry.publisher ?? null,
    license: registry.license ?? null,
    scope_label: registry.coverage?.scope_label ?? null,
    state: state ?? null,
    freshness,
    last_successful_refresh: lastMs === null ? null : new Date(lastMs).toISOString(),
    data_age_days: lastMs === null ? null : round1((nowMs - lastMs) / DAY_MS),
    record_count: recordCount,
    cell_count: cellList.length,
    known_gaps: [
      {
        key: 'non_placeable_rows',
        count: nonPlaceable,
        detail:
          `${nonPlaceable} normalized row(s) had no usable coordinates; kept and flagged ` +
          `(gap=missing_coordinates|invalid_coordinates), never dropped, and not placed on the map.`,
      },
      {
        key: 'city_of_poway_permits',
        detail:
          registry.coverage?.open_gap ??
          'No public dataset/API for incorporated City of Poway permits; treat as an open gap ' +
            'requiring owner/agency contact. Absence of a feed is not evidence that no permits exist.',
      },
    ],
  };

  const publishedDir = join(baseDir, 'published');
  await mkdir(publishedDir, { recursive: true });
  await mkdir(publicDir, { recursive: true });

  const cellsBytes = JSON.stringify(geojson, null, 2);
  const freshBytes = JSON.stringify(freshnessDoc, null, 2);

  const paths = {
    publishedCells: join(publishedDir, `${id}.cells.geojson`),
    publishedFreshness: join(publishedDir, `${id}.freshness.json`),
    publicCells: join(publicDir, 'cells.geojson'),
    publicFreshness: join(publicDir, 'freshness.json'),
  };

  await writeFile(paths.publishedCells, cellsBytes);
  await writeFile(paths.publishedFreshness, freshBytes);
  await writeFile(paths.publicCells, cellsBytes);
  await writeFile(paths.publicFreshness, freshBytes);

  return { geojson, freshness: freshnessDoc, paths };
}
