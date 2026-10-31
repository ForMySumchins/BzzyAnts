import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DEFAULT_OBSERVATION_STATUS,
  OBSERVATION_STATUSES,
  OBSERVATION_STATUS_LABEL,
  ObservationError,
  observationsForTarget,
  type ObservationStatus,
  type ObservationTargetKind,
} from "@/lib/observations/storage";
import { useObservationStore, useObservationsLoader } from "@/lib/observations/use-observations";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<ObservationStatus, "default" | "warn" | "ok"> = {
  unreviewed: "default",
  "follow-up-needed": "warn",
  complete: "ok",
};

const TARGET_KIND_LABEL: Record<ObservationTargetKind, string> = {
  site: "Site",
  pin: "Pin",
};

function formatTimestamp(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/**
 * Field observations for the currently selected map feature (catalog site or
 * dropped pin). Render with `key={targetId}` so a draft never carries over to
 * a different feature.
 */
export function ObservationsSection({
  targetId,
  targetKind,
  targetLabel,
}: {
  targetId: string;
  targetKind: ObservationTargetKind;
  targetLabel: string;
}) {
  useObservationsLoader();
  const state = useObservationStore((s) => s.state);
  const save = useObservationStore((s) => s.save);

  const uid = useId();
  const formId = `${uid}-form`;
  const noteId = `${uid}-note`;
  const noteErrorId = `${uid}-note-error`;
  const saveErrorId = `${uid}-save-error`;
  const headingId = `${uid}-heading`;

  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<ObservationStatus>(DEFAULT_OBSERVATION_STATUS);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const openButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(false);

  useEffect(() => {
    if (open) noteRef.current?.focus();
    else if (returnFocus.current) {
      returnFocus.current = false;
      openButtonRef.current?.focus();
    }
  }, [open]);

  const items = state.phase === "ready" ? observationsForTarget(state.observations, targetId) : [];
  const blocked = state.phase === "error";

  function openForm() {
    setSavedMessage(null);
    setSaveError(null);
    setOpen(true);
  }

  function closeForm() {
    returnFocus.current = true;
    setOpen(false);
    setNote("");
    setStatus(DEFAULT_OBSERVATION_STATUS);
    setNoteError(null);
    setSaveError(null);
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (savingRef.current) return; // guard against double submit
    setSaveError(null);
    if (!note.trim()) {
      setNoteError("Enter a note before saving.");
      noteRef.current?.focus();
      return;
    }
    savingRef.current = true;
    setSaving(true);
    try {
      save({ targetId, targetKind, targetLabel, note, status });
      // Only reached when storage confirmed the write.
      returnFocus.current = true;
      setOpen(false);
      setNote("");
      setStatus(DEFAULT_OBSERVATION_STATUS);
      setNoteError(null);
      setSavedMessage(`Observation saved to this device for ${targetLabel}.`);
      toast("Observation saved on this device");
    } catch (err) {
      // Keep the draft so nothing typed is lost.
      const message =
        err instanceof ObservationError ? err.message : "Not saved: an unexpected error occurred.";
      if (err instanceof ObservationError && err.code === "validation") setNoteError(message);
      else setSaveError(message);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3
          id={headingId}
          className="font-mono text-[10px] uppercase tracking-[0.18em] text-subtle"
        >
          Field observations
        </h3>
        {state.phase === "ready" && (
          <span className="font-mono text-[10px] tabular-nums text-subtle">{items.length}</span>
        )}
      </div>

      <p className="text-xs leading-relaxed text-muted">
        Saved only in this browser on this device. Not synced or backed up; clearing browser data
        deletes them.
      </p>

      {state.phase === "loading" && <p className="text-sm text-muted">Loading observations…</p>}

      {blocked && (
        <p
          role="alert"
          className="rounded-sm border border-danger/40 px-3 py-2 text-sm leading-relaxed text-danger"
        >
          {state.message}
        </p>
      )}

      {state.phase === "ready" && state.skipped > 0 && (
        <p className="rounded-sm border border-warn/40 px-3 py-2 text-xs leading-relaxed text-warn">
          {state.skipped} stored {state.skipped === 1 ? "record" : "records"} could not be read and
          {state.skipped === 1 ? " was" : " were"} left untouched.
        </p>
      )}

      <p role="status" aria-live="polite" className={cn("text-sm text-ok", !savedMessage && "sr-only")}>
        {savedMessage ?? ""}
      </p>

      {!open && state.phase === "ready" && (
        <Button
          ref={openButtonRef}
          variant="outline"
          size="sm"
          className="self-start"
          onClick={openForm}
        >
          <Plus className="size-3.5" />
          Add observation
        </Button>
      )}

      {open && state.phase === "ready" && (
        <form
          id={formId}
          onSubmit={onSubmit}
          noValidate
          aria-label={`New observation for ${targetLabel}`}
          className="flex flex-col gap-3 rounded-sm border border-border bg-raised/40 p-3"
        >
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-subtle">
              For {TARGET_KIND_LABEL[targetKind]}
            </p>
            <p className="text-sm font-medium leading-snug">{targetLabel}</p>
            <p className="font-mono text-[10px] text-subtle break-all">ID {targetId}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor={noteId} className="text-sm text-fg">
              Note <span className="text-subtle">(required)</span>
            </label>
            <textarea
              ref={noteRef}
              id={noteId}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                if (noteError && e.target.value.trim()) setNoteError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
              rows={4}
              required
              aria-required="true"
              aria-invalid={noteError ? true : undefined}
              aria-describedby={noteError ? noteErrorId : undefined}
              placeholder="What did you observe?"
              className={cn(
                "rounded-sm border bg-raised px-3 py-2 text-base text-fg placeholder:text-subtle md:text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60",
                noteError ? "border-danger/60" : "border-border",
              )}
            />
            {noteError && (
              <p id={noteErrorId} className="text-xs text-danger">
                {noteError}
              </p>
            )}
          </div>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-sm text-fg">
              Status <span className="text-subtle">(provisional list)</span>
            </legend>
            <div className="grid grid-cols-3 rounded-sm border border-border">
              {OBSERVATION_STATUSES.map((s) => (
                <label
                  key={s}
                  className={cn(
                    "flex min-h-11 cursor-pointer items-center justify-center px-1.5 py-1 text-center font-mono text-[10px] uppercase leading-tight tracking-wider",
                    "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-inset has-[:focus-visible]:ring-accent/60",
                    status === s ? "bg-raised text-fg" : "text-subtle hover:text-fg",
                  )}
                >
                  <input
                    type="radio"
                    name={`${uid}-status`}
                    value={s}
                    checked={status === s}
                    onChange={() => setStatus(s)}
                    className="sr-only"
                  />
                  {OBSERVATION_STATUS_LABEL[s]}
                </label>
              ))}
            </div>
          </fieldset>

          {saveError && (
            <p
              id={saveErrorId}
              role="alert"
              className="rounded-sm border border-danger/40 px-3 py-2 text-sm leading-relaxed text-danger"
            >
              {saveError}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              size="default"
              disabled={saving}
              aria-describedby={saveError ? saveErrorId : undefined}
            >
              {saving ? "Saving…" : "Save observation"}
            </Button>
            <Button type="button" variant="outline" size="default" onClick={closeForm}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {state.phase === "ready" &&
        (items.length > 0 ? (
          <ul className="flex flex-col gap-3" aria-label={`Observations for ${targetLabel}`}>
            {items.map((o) => (
              <li key={o.id} className="border-l border-border pl-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={STATUS_BADGE[o.status]}>{OBSERVATION_STATUS_LABEL[o.status]}</Badge>
                  <time
                    dateTime={o.createdAt}
                    className="font-mono text-[10px] tabular-nums text-subtle"
                  >
                    {formatTimestamp(o.createdAt)}
                  </time>
                </div>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-fg">
                  {o.note}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          !open && <p className="text-sm text-muted">No observations for this {targetKind} yet.</p>
        ))}
    </section>
  );
}
