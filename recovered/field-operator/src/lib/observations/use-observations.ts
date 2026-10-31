import { useEffect } from "react";
import { create } from "zustand";
import {
  OBSERVATION_STORAGE_KEY,
  ObservationError,
  getBrowserStorage,
  loadObservations,
  saveObservation,
  type NewObservationInput,
  type Observation,
  type ObservationErrorCode,
} from "./storage";

export type ObservationLoadState =
  | { phase: "loading" }
  | { phase: "ready"; observations: Observation[]; skipped: number }
  | { phase: "error"; code: ObservationErrorCode; message: string };

interface ObservationStore {
  state: ObservationLoadState;
  load: () => void;
  /** Persists first; only updates in-memory state after storage confirmed it. Throws ObservationError. */
  save: (input: NewObservationInput) => Observation;
}

function toObservationError(err: unknown): ObservationError {
  if (err instanceof ObservationError) return err;
  return new ObservationError("write-failed", "Not saved: an unexpected storage error occurred.");
}

// Not persisted through zustand/persist on purpose: that middleware does not
// surface storage failures, and the UI must not report success unless the
// write actually landed.
export const useObservationStore = create<ObservationStore>()((set) => ({
  state: { phase: "loading" },
  load: () => {
    try {
      const { observations, skipped } = loadObservations(getBrowserStorage());
      set({ state: { phase: "ready", observations, skipped } });
    } catch (err) {
      const e = toObservationError(err);
      set({ state: { phase: "error", code: e.code, message: e.message } });
    }
  },
  save: (input) => {
    try {
      const result = saveObservation(getBrowserStorage(), input);
      set({
        state: { phase: "ready", observations: result.observations, skipped: result.skipped },
      });
      return result.saved;
    } catch (err) {
      const e = toObservationError(err);
      // Data we refuse to overwrite should also block the UI going forward.
      if (e.code === "unreadable" || e.code === "unsupported-version" || e.code === "unavailable") {
        set({ state: { phase: "error", code: e.code, message: e.message } });
      }
      throw e;
    }
  },
}));

/** Loads observations on the client and follows changes made in other tabs. */
export function useObservationsLoader() {
  const load = useObservationStore((s) => s.load);
  useEffect(() => {
    load();
    function onStorage(e: StorageEvent) {
      if (e.key === null || e.key === OBSERVATION_STORAGE_KEY) load();
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [load]);
}
