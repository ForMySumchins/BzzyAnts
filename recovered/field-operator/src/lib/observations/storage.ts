/**
 * Field observations — local-device persistence.
 *
 * Observations are stored in this browser's localStorage under a versioned
 * envelope. Nothing is synced or backed up. The module is framework-free so it
 * can be exercised with `node --test` (no `@/` path aliases here).
 *
 * Observations are associated with an existing selectable map feature (a
 * catalog site or a dropped pin) by its stable id. This package has no H3
 * integration, so there is no H3 cell id.
 *
 * Safety rules:
 * - Stored data we cannot understand (malformed JSON, unknown envelope version)
 *   is never overwritten: loads report an error and saves are refused.
 * - Individual records that fail validation are hidden from the UI but kept
 *   verbatim in storage when new records are appended.
 * - A save only returns after `setItem` succeeded and a read-back matched.
 */

export const OBSERVATION_STORAGE_KEY = "bzzy-field-observations";
export const OBSERVATION_STORAGE_VERSION = 1;

/**
 * PROVISIONAL status vocabulary. No observation statuses exist in the product
 * sources yet; replace these once the product defines them.
 */
export const OBSERVATION_STATUSES = ["unreviewed", "follow-up-needed", "complete"] as const;
export type ObservationStatus = (typeof OBSERVATION_STATUSES)[number];
export const OBSERVATION_STATUS_LABEL: Record<ObservationStatus, string> = {
  unreviewed: "Unreviewed",
  "follow-up-needed": "Follow-up needed",
  complete: "Complete",
};
export const DEFAULT_OBSERVATION_STATUS: ObservationStatus = "unreviewed";

export const OBSERVATION_TARGET_KINDS = ["site", "pin"] as const;
export type ObservationTargetKind = (typeof OBSERVATION_TARGET_KINDS)[number];

export interface Observation {
  id: string;
  /** Stable id of the selected map feature (catalog site id or pin id). */
  targetId: string;
  targetKind: ObservationTargetKind;
  /** Feature label as displayed when the observation was saved. */
  targetLabel: string;
  note: string;
  status: ObservationStatus;
  createdAt: string;
  updatedAt: string;
}

export interface NewObservationInput {
  targetId: string;
  targetKind: string;
  targetLabel: string;
  note: string;
  status: string;
}

export type ObservationErrorCode =
  | "validation"
  | "unavailable"
  | "unreadable"
  | "unsupported-version"
  | "quota"
  | "write-failed";

export class ObservationError extends Error {
  code: ObservationErrorCode;
  constructor(code: ObservationErrorCode, message: string) {
    super(message);
    this.name = "ObservationError";
    this.code = code;
  }
}

/** Minimal Storage surface we depend on (lets tests inject a fake). */
export type KeyValueStorage = Pick<Storage, "getItem" | "setItem">;

export interface LoadedObservations {
  observations: Observation[];
  /** Stored records that failed validation; left untouched in storage. */
  skipped: number;
}

interface Envelope {
  version: number;
  observations: unknown[];
  [extra: string]: unknown;
}

const UNAVAILABLE_MESSAGE =
  "This browser is blocking local storage, so observations cannot be loaded or saved.";
const UNREADABLE_MESSAGE =
  "Saved observations on this device are unreadable. They were left untouched and new saves are paused to avoid overwriting them.";

export function isObservationStatus(value: unknown): value is ObservationStatus {
  return typeof value === "string" && (OBSERVATION_STATUSES as readonly string[]).includes(value);
}

export function isObservationTargetKind(value: unknown): value is ObservationTargetKind {
  return (
    typeof value === "string" && (OBSERVATION_TARGET_KINDS as readonly string[]).includes(value)
  );
}

function isIsoDate(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && !Number.isNaN(Date.parse(value));
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function isValidObservation(value: unknown): value is Observation {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  return (
    nonEmptyString(r.id) &&
    nonEmptyString(r.targetId) &&
    isObservationTargetKind(r.targetKind) &&
    typeof r.targetLabel === "string" &&
    nonEmptyString(r.note) &&
    isObservationStatus(r.status) &&
    isIsoDate(r.createdAt) &&
    isIsoDate(r.updatedAt)
  );
}

/** Returns window.localStorage, or null when it is missing or access throws. */
export function getBrowserStorage(): KeyValueStorage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

function readRaw(storage: KeyValueStorage | null): string | null {
  if (!storage) throw new ObservationError("unavailable", UNAVAILABLE_MESSAGE);
  try {
    return storage.getItem(OBSERVATION_STORAGE_KEY);
  } catch {
    throw new ObservationError("unavailable", UNAVAILABLE_MESSAGE);
  }
}

/** Parse the stored envelope. Throws rather than guessing at unknown data. */
function parseEnvelope(raw: string | null): Envelope {
  if (raw === null) return { version: OBSERVATION_STORAGE_VERSION, observations: [] };
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new ObservationError("unreadable", UNREADABLE_MESSAGE);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new ObservationError("unreadable", UNREADABLE_MESSAGE);
  }
  const env = parsed as Record<string, unknown>;
  if (env.version !== OBSERVATION_STORAGE_VERSION) {
    throw new ObservationError(
      "unsupported-version",
      `Saved observations use an unsupported format (version ${String(env.version)}). They were left untouched and new saves are paused.`,
    );
  }
  if (!Array.isArray(env.observations)) {
    throw new ObservationError("unreadable", UNREADABLE_MESSAGE);
  }
  return env as Envelope;
}

function summarize(env: Envelope): LoadedObservations {
  const observations: Observation[] = [];
  let skipped = 0;
  for (const record of env.observations) {
    if (isValidObservation(record)) observations.push(record);
    else skipped += 1;
  }
  return { observations, skipped };
}

export function loadObservations(storage: KeyValueStorage | null): LoadedObservations {
  return summarize(parseEnvelope(readRaw(storage)));
}

/** Newest first, only for the given target. */
export function observationsForTarget(
  observations: readonly Observation[],
  targetId: string,
): Observation[] {
  return observations
    .filter((o) => o.targetId === targetId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

function defaultId(): string {
  // randomUUID is only exposed in secure contexts; LAN/mobile testing over
  // plain http falls back to a timestamp + random suffix.
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (c && typeof c.randomUUID === "function") return `obs-${c.randomUUID()}`;
  return `obs-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function isQuotaError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const e = err as { name?: string; code?: number };
  return (
    e.name === "QuotaExceededError" ||
    e.name === "NS_ERROR_DOM_QUOTA_REACHED" ||
    e.code === 22 ||
    e.code === 1014
  );
}

export interface SaveOptions {
  now?: () => Date;
  makeId?: () => string;
}

export interface SaveResult extends LoadedObservations {
  saved: Observation;
}

/**
 * Validate and append one observation. Re-reads storage right before writing so
 * records saved by another tab are preserved. Throws ObservationError on any
 * validation or persistence failure; in that case nothing new is reported saved.
 */
export function saveObservation(
  storage: KeyValueStorage | null,
  input: NewObservationInput,
  options: SaveOptions = {},
): SaveResult {
  const targetId = typeof input.targetId === "string" ? input.targetId.trim() : "";
  const note = typeof input.note === "string" ? input.note.trim() : "";
  if (!targetId || !isObservationTargetKind(input.targetKind)) {
    throw new ObservationError("validation", "Select a site or pin before saving an observation.");
  }
  if (!note) {
    throw new ObservationError("validation", "Enter a note before saving.");
  }
  if (!isObservationStatus(input.status)) {
    throw new ObservationError("validation", "Choose a status before saving.");
  }

  const env = parseEnvelope(readRaw(storage));

  const existingIds = new Set(
    env.observations
      .map((r) => (r && typeof r === "object" ? (r as { id?: unknown }).id : undefined))
      .filter((id): id is string => typeof id === "string"),
  );
  const makeId = options.makeId ?? defaultId;
  let id = makeId();
  for (let i = 0; existingIds.has(id) && i < 5; i++) id = makeId();
  if (existingIds.has(id)) {
    throw new ObservationError("write-failed", "Could not create a unique observation id. Try again.");
  }

  const timestamp = (options.now ?? (() => new Date()))().toISOString();
  const saved: Observation = {
    id,
    targetId,
    targetKind: input.targetKind,
    targetLabel: typeof input.targetLabel === "string" ? input.targetLabel.trim() : "",
    note,
    status: input.status,
    createdAt: timestamp,
    updatedAt: timestamp,
  };

  // Keep any unknown top-level fields and every existing record verbatim.
  const next: Envelope = { ...env, observations: [...env.observations, saved] };
  const serialized = JSON.stringify(next);

  try {
    storage!.setItem(OBSERVATION_STORAGE_KEY, serialized);
  } catch (err) {
    if (isQuotaError(err)) {
      throw new ObservationError(
        "quota",
        "Not saved: this device's browser storage is full. Your note is still in the form.",
      );
    }
    throw new ObservationError(
      "write-failed",
      "Not saved: the browser refused to write to local storage. Your note is still in the form.",
    );
  }

  let readBack: string | null;
  try {
    readBack = storage!.getItem(OBSERVATION_STORAGE_KEY);
  } catch {
    readBack = null;
  }
  if (readBack !== serialized) {
    throw new ObservationError(
      "write-failed",
      "Not saved: the observation could not be confirmed in local storage. Your note is still in the form.",
    );
  }

  return { saved, ...summarize(next) };
}
