// H3 aggregation + month-over-month deltas for canonical permit rows.
//
// Canonical (lowercase-hex) H3 index strings are our stable cell ids (D-001).
// Includes Audit Packet P3 / F09 correction: computeDeltas preserves the union of
// current and prior cells so prior-only cells represent declines instead of vanishing.
//
// Pure and side-effect free: no file or network I/O.

import { latLngToCell } from 'h3-js';

/** Compare two timestamp-ish strings; true when `a` is strictly newer than `b`. */
function isNewer(a, b) {
  const ta = Date.parse(a);
  const tb = Date.parse(b);
  if (Number.isNaN(ta)) return false;
  if (Number.isNaN(tb)) return true;
  return ta > tb;
}

/** Round to one decimal place (keeps delta_pct readable). */
function round1(n) {
  return Math.round(n * 10) / 10;
}

/**
 * Aggregate canonical rows into H3 cells.
 *
 * @param {object[]} canonicalRows  Output of normalizeRows().rows
 * @param {object}   [opts]
 * @param {number}   [opts.resolution=8]  H3 resolution for the territory.
 * @returns {Array<{ h3:string, count:number, last_activity:string|null, scope_label:string|null }>}
 */
export function aggregateToH3(canonicalRows, { resolution = 8 } = {}) {
  const cells = new Map();
  for (const row of Array.isArray(canonicalRows) ? canonicalRows : []) {
    if (!row || row.placeable !== true) continue;
    const { latitude, longitude } = row;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;

    const h3 = latLngToCell(latitude, longitude, resolution);

    const entry = cells.get(h3) || {
      h3,
      count: 0,
      last_activity: null,
      scope_label: row.scope_label ?? null,
    };
    entry.count += 1;
    if (isNewer(row.last_updated, entry.last_activity)) {
      entry.last_activity = row.last_updated ?? entry.last_activity;
    }
    if (!entry.scope_label && row.scope_label) entry.scope_label = row.scope_label;
    cells.set(h3, entry);
  }

  return [...cells.values()].sort((a, b) =>
    a.h3 < b.h3 ? -1 : a.h3 > b.h3 ? 1 : 0
  );
}

/**
 * Merge current cells against a prior run, by h3 (Fixes F09).
 *
 * Evaluates the union of current and prior H3 cells so that cells present in the
 * prior snapshot but absent in the current snapshot are emitted with count=0 and
 * negative delta rather than silently disappearing.
 *
 * @param {Array<{h3:string,count:number}>} currentCells
 * @param {Array<{h3:string,count:number}>} priorCells
 * @returns {Array<object>} union of cells enriched with { prior_count, delta, delta_pct }
 */
export function computeDeltas(currentCells, priorCells) {
  const prior = new Map();
  const priorMeta = new Map();
  for (const c of Array.isArray(priorCells) ? priorCells : []) {
    if (c && typeof c.h3 === 'string') {
      prior.set(c.h3, Number.isFinite(c.count) ? c.count : 0);
      priorMeta.set(c.h3, c);
    }
  }

  const seen = new Set();
  const results = [];

  for (const cell of Array.isArray(currentCells) ? currentCells : []) {
    if (!cell || typeof cell.h3 !== 'string') continue;
    seen.add(cell.h3);
    const prior_count = prior.has(cell.h3) ? prior.get(cell.h3) : 0;
    const delta = cell.count - prior_count;
    const delta_pct = prior_count === 0 ? null : round1((delta / prior_count) * 100);
    results.push({ ...cell, prior_count, delta, delta_pct });
  }

  // Emit prior-only cells that dropped to 0 in current snapshot (Fixes F09)
  for (const [h3Key, priorCount] of prior.entries()) {
    if (!seen.has(h3Key)) {
      const meta = priorMeta.get(h3Key) || {};
      const delta = 0 - priorCount;
      const delta_pct = priorCount === 0 ? null : round1((delta / priorCount) * 100);
      results.push({
        h3: h3Key,
        count: 0,
        last_activity: meta.last_activity ?? null,
        scope_label: meta.scope_label ?? null,
        prior_count: priorCount,
        delta,
        delta_pct,
      });
    }
  }

  return results.sort((a, b) => (a.h3 < b.h3 ? -1 : a.h3 > b.h3 ? 1 : 0));
}
