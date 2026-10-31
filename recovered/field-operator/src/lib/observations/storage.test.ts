import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  OBSERVATION_STORAGE_KEY,
  ObservationError,
  loadObservations,
  observationsForTarget,
  saveObservation,
  type KeyValueStorage,
} from "./storage.ts";

class MemoryStorage implements KeyValueStorage {
  data = new Map<string, string>();
  failWrites: Error | null = null;
  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }
  setItem(key: string, value: string): void {
    if (this.failWrites) throw this.failWrites;
    this.data.set(key, value);
  }
}

const fixedNow = () => new Date("2026-10-04T12:00:00.000Z");
let seq = 0;
const nextId = () => `obs-test-${++seq}`;

function site(note: string, status = "unreviewed", targetId = "pentagon") {
  return { targetId, targetKind: "site", targetLabel: "Pentagon", note, status };
}

function expectCode(fn: () => unknown, code: string) {
  assert.throws(fn, (err: unknown) => err instanceof ObservationError && err.code === code);
}

describe("observation storage", () => {
  it("saves a trimmed observation in a versioned envelope and reloads it", () => {
    const storage = new MemoryStorage();
    const result = saveObservation(storage, site("  Gate 3 closed  ", "follow-up-needed"), {
      now: fixedNow,
      makeId: nextId,
    });
    assert.equal(result.saved.note, "Gate 3 closed");
    assert.equal(result.saved.targetId, "pentagon");
    assert.equal(result.saved.targetKind, "site");
    assert.equal(result.saved.targetLabel, "Pentagon");
    assert.equal(result.saved.status, "follow-up-needed");
    assert.equal(result.saved.createdAt, "2026-10-04T12:00:00.000Z");
    assert.equal(result.saved.updatedAt, result.saved.createdAt);

    const stored = JSON.parse(storage.getItem(OBSERVATION_STORAGE_KEY) as string);
    assert.equal(stored.version, 1);
    assert.equal(stored.observations.length, 1);

    // A fresh load (as after a page refresh) returns the same record.
    const reloaded = loadObservations(storage);
    assert.deepEqual(reloaded.observations, [result.saved]);
    assert.equal(reloaded.skipped, 0);
  });

  it("rejects empty notes, missing targets and unknown statuses without writing", () => {
    const storage = new MemoryStorage();
    expectCode(() => saveObservation(storage, site("   ")), "validation");
    expectCode(() => saveObservation(storage, site("ok", "unreviewed", " ")), "validation");
    expectCode(
      () => saveObservation(storage, { ...site("ok"), targetKind: "h3" }),
      "validation",
    );
    expectCode(() => saveObservation(storage, site("ok", "done")), "validation");
    assert.equal(storage.getItem(OBSERVATION_STORAGE_KEY), null);
  });

  it("lists observations only for the selected target, newest first", () => {
    const storage = new MemoryStorage();
    let t = Date.parse("2026-10-04T12:00:00.000Z");
    const now = () => new Date((t += 1000));
    saveObservation(storage, site("A1"), { now, makeId: nextId });
    saveObservation(storage, site("B1", "complete", "ns-norfolk"), { now, makeId: nextId });
    saveObservation(storage, site("A2"), { now, makeId: nextId });
    const { observations } = loadObservations(storage);
    assert.deepEqual(
      observationsForTarget(observations, "pentagon").map((o) => o.note),
      ["A2", "A1"],
    );
    assert.deepEqual(
      observationsForTarget(observations, "ns-norfolk").map((o) => o.note),
      ["B1"],
    );
    assert.deepEqual(observationsForTarget(observations, "pin-x"), []);
  });

  it("preserves invalid records and unknown fields when appending", () => {
    const storage = new MemoryStorage();
    const bad = { id: "legacy", note: 42 };
    storage.setItem(
      OBSERVATION_STORAGE_KEY,
      JSON.stringify({ version: 1, exportedBy: "someone", observations: [bad] }),
    );
    const loaded = loadObservations(storage);
    assert.equal(loaded.observations.length, 0);
    assert.equal(loaded.skipped, 1);

    const result = saveObservation(storage, site("new"), { now: fixedNow, makeId: nextId });
    assert.equal(result.skipped, 1);
    const stored = JSON.parse(storage.getItem(OBSERVATION_STORAGE_KEY) as string);
    assert.equal(stored.exportedBy, "someone");
    assert.deepEqual(stored.observations[0], bad);
    assert.equal(stored.observations.length, 2);
  });

  for (const [label, raw, code] of [
    ["malformed JSON", "{not json", "unreadable"],
    ["a non-envelope value", "[1,2,3]", "unreadable"],
    ["an unsupported version", JSON.stringify({ version: 2, observations: [] }), "unsupported-version"],
  ] as const) {
    it(`refuses to load or overwrite ${label}`, () => {
      const storage = new MemoryStorage();
      storage.setItem(OBSERVATION_STORAGE_KEY, raw);
      expectCode(() => loadObservations(storage), code);
      expectCode(() => saveObservation(storage, site("x")), code);
      assert.equal(storage.getItem(OBSERVATION_STORAGE_KEY), raw);
    });
  }

  it("reports quota and other write failures instead of success", () => {
    const storage = new MemoryStorage();
    saveObservation(storage, site("first"), { now: fixedNow, makeId: nextId });
    const before = storage.getItem(OBSERVATION_STORAGE_KEY);

    const quota = new Error("full");
    quota.name = "QuotaExceededError";
    storage.failWrites = quota;
    expectCode(() => saveObservation(storage, site("second")), "quota");

    storage.failWrites = new Error("SecurityError");
    expectCode(() => saveObservation(storage, site("second")), "write-failed");

    assert.equal(storage.getItem(OBSERVATION_STORAGE_KEY), before);
    assert.equal(loadObservations(storage).observations.length, 1);
  });

  it("reports a failure when the write cannot be read back", () => {
    const storage = new MemoryStorage();
    storage.setItem = () => {}; // silently drops writes
    expectCode(() => saveObservation(storage, site("lost")), "write-failed");
  });

  it("reports unavailable storage", () => {
    expectCode(() => loadObservations(null), "unavailable");
    expectCode(() => saveObservation(null, site("x")), "unavailable");
    const throwing: KeyValueStorage = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {},
    };
    expectCode(() => loadObservations(throwing), "unavailable");
  });

  it("never reuses an existing observation id", () => {
    const storage = new MemoryStorage();
    const ids = ["dup", "dup", "fresh"];
    saveObservation(storage, site("one"), { now: fixedNow, makeId: () => "dup" });
    const r = saveObservation(storage, site("two"), { now: fixedNow, makeId: () => ids.shift()! });
    assert.equal(r.saved.id, "fresh");
  });
});
