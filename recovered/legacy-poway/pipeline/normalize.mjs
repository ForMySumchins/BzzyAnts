// Normalize raw Socrata-shaped permit rows into canonical pipeline rows.
//
// Rules (see the source registry + decision D-004 + Audit Packet P3 / F11):
//   - Stamp every row with the source scope label `sd_county_pds; postal_city=POWAY`.
//     NEVER `city:poway` — these are County-PDS postal-Poway permits, not permits
//     issued by the incorporated City of Poway.
//   - De-duplicate by composite `source + record_id`, keeping the row with the NEWEST
//     `last_updated` so mixed-source feeds never collide on raw numeric IDs.
//   - Enforce geographic coordinate bounds (-90 <= lat <= 90, -180 <= lng <= 180).
//     Rows with missing or out-of-range coordinates are KEPT and flagged
//     (`placeable:false, gap:'missing_coordinates' | 'invalid_coordinates'`).
//
// Pure and side-effect free: no file or network I/O.

/** True only for real, finite numbers (rejects NaN, strings, null, booleans). */
function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

/** True only when lat/lng are finite numbers within valid Earth bounds (Fixes F11). */
function isValidLatLng(lat, lng) {
  return (
    isFiniteNumber(lat) &&
    isFiniteNumber(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

/** Compare two timestamp-ish strings; true when `a` is strictly newer than `b`. */
function isNewer(a, b) {
  const ta = Date.parse(a);
  const tb = Date.parse(b);
  if (Number.isNaN(ta)) return false;
  if (Number.isNaN(tb)) return true;
  return ta > tb;
}

/** Project one raw row onto the canonical shape. */
function toCanonical(row, scopeLabel) {
  const isObj = row !== null && typeof row === 'object';
  const geo = isObj ? row.geocoded_column : undefined;
  const lat = geo && typeof geo === 'object' ? geo.latitude : undefined;
  const lng = geo && typeof geo === 'object' ? geo.longitude : undefined;
  const hasNumbers = isFiniteNumber(lat) && isFiniteNumber(lng);
  const placeable = isValidLatLng(lat, lng);

  let gap = null;
  if (!placeable) {
    gap = hasNumbers ? 'invalid_coordinates' : 'missing_coordinates';
  }

  return {
    record_id: isObj && row.record_id != null ? row.record_id : null,
    source_id: isObj && row.source != null ? String(row.source) : null,
    last_updated: isObj && row.last_updated != null ? row.last_updated : null,
    latitude: placeable ? lat : null,
    longitude: placeable ? lng : null,
    placeable,
    gap,
    scope_label: scopeLabel,
    record_type: isObj && row.record_type != null ? row.record_type : null,
    record_category: isObj && row.record_category != null ? row.record_category : null,
  };
}

/**
 * Normalize raw rows against a source registry.
 *
 * @param {unknown[]} rows      Raw source rows.
 * @param {object}    registry  Source registry (provides coverage.scope_label).
 * @returns {{ rows: object[], stats: object }}
 */
export function normalizeRows(rows, registry) {
  const scopeLabel = registry?.coverage?.scope_label ?? null;
  const defaultSource = registry?.id ?? 'default_source';
  const list = Array.isArray(rows) ? rows : [];

  const byId = new Map();
  let input = 0;
  let noId = 0;
  list.forEach((row) => {
    input += 1;
    const canonical = toCanonical(row, scopeLabel);
    const srcNamespace = canonical.source_id || defaultSource;
    let key;
    if (canonical.record_id != null) {
      key = `${srcNamespace}:id:${canonical.record_id}`;
    } else {
      key = `${srcNamespace}:noid:${noId}`;
      noId += 1;
    }
    const held = byId.get(key);
    if (!held || isNewer(canonical.last_updated, held.last_updated)) {
      byId.set(key, canonical);
    }
  });

  const out = [...byId.values()];
  const placeable = out.filter((r) => r.placeable).length;
  const nonPlaceable = out.length - placeable;

  const stats = {
    input,
    output: out.length,
    duplicates_removed: input - out.length,
    placeable,
    non_placeable: nonPlaceable,
    scope_label: scopeLabel,
  };

  return { rows: out, stats };
}
