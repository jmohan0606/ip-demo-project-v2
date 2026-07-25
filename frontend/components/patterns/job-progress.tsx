"use client";
/**
 * R11 C2/C3 — async job progress for Regenerate (commentary) and Rescan
 * (anomalies).
 *
 * useAsyncJob(): starts a job via the async POST, then POLLS the status
 * endpoint (1.5s, GET-only — polling never re-triggers the job). On
 * completion it fires onComplete so the screen can refresh to the new
 * version/scan without a manual reload; on failure the reason stays visible
 * until dismissed. Reopening the screen mid-run REJOINS the running job
 * (rejoin() checks the status endpoint once on mount) — the job itself runs
 * server-side in a daemon thread and survives the browser closing.
 *
 * JobProgressOverlay: a NON-BLOCKING floating card (bottom-right) — the page
 * stays usable while the system visibly works ("advisor 3 of 10").
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { JobStart, JobStatus } from "@/lib/api/v2";

const POLL_MS = 1500;

export interface AsyncJob {
  /** Overlay visibility + latest polled status. */
  visible: boolean;
  status: JobStatus | null;
  running: boolean;
  /** Kick off a job (no-op while one is running — C3). */
  start: (post: () => Promise<JobStart>) => void;
  /** Hide the overlay (only offered on failure / completion). */
  dismiss: () => void;
}

export function useAsyncJob(
  getStatus: () => Promise<JobStatus>,
  onComplete: (status: JobStatus) => void,
): AsyncJob {
  const [visible, setVisible] = useState(false);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const running = status?.state === "starting" || status?.state === "running";
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completedFor = useRef<string | null>(null); // job_id already completed
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const getStatusRef = useRef(getStatus);
  getStatusRef.current = getStatus;

  const stopPolling = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const poll = useCallback(() => {
    stopPolling();
    timer.current = setTimeout(() => {
      getStatusRef.current()
        .then((s) => {
          setStatus(s);
          if (s.state === "starting" || s.state === "running") {
            poll(); // keep polling — never re-POST (C3)
          } else if (s.state === "completed") {
            if (s.job_id && completedFor.current !== s.job_id) {
              completedFor.current = s.job_id ?? null;
              onCompleteRef.current(s);
            }
            // brief success flash, then hide
            timer.current = setTimeout(() => setVisible(false), 2500);
          }
          // failed: overlay stays until dismissed (C2 — never a silent dismiss)
        })
        .catch(() => poll()); // transient status fetch error: keep trying
    }, POLL_MS);
  }, [stopPolling]);

  const start = useCallback((post: () => Promise<JobStart>) => {
    if (running) return; // C3 — a click while running never re-triggers
    setVisible(true);
    setStatus({ state: "starting" });
    post()
      .then((r) => {
        setStatus({ state: (r.state as JobStatus["state"]) ?? "starting", job_id: r.job_id });
        poll();
      })
      .catch((e: unknown) => {
        setStatus({ state: "failed", error: e instanceof Error ? e.message : "Failed to start." });
      });
  }, [running, poll]);

  // Mid-run rejoin (C3): if a job is already running when the screen opens,
  // show the overlay and resume polling — never start a new job.
  useEffect(() => {
    let active = true;
    getStatusRef.current()
      .then((s) => {
        if (!active) return;
        if (s.state === "starting" || s.state === "running") {
          completedFor.current = null;
          setStatus(s);
          setVisible(true);
          poll();
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
      stopPolling();
    };
  }, [poll, stopPolling]);

  return {
    visible,
    status,
    running,
    start,
    dismiss: () => setVisible(false),
  };
}

export function JobProgressOverlay({
  job,
  title,
  doneLabel,
}: {
  job: AsyncJob;
  /** e.g. "Generating commentary" / "Scanning for anomalies" */
  title: string;
  /** e.g. "Commentary regenerated — showing the latest version" */
  doneLabel: string;
}) {
  if (!job.visible || !job.status) return null;
  const s = job.status;
  const failed = s.state === "failed";
  const done = s.state === "completed";
  const progress =
    s.advisor_total && s.advisor_index
      ? `advisor ${s.advisor_index} of ${s.advisor_total}`
      : "";
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 w-[340px] rounded-[4px] border bg-white shadow-lg print:hidden"
      style={{ borderColor: failed ? "var(--v2-negative, #b3261e)" : "var(--v2-border, #d7dbe0)" }}
    >
      <div className="flex items-start gap-3 p-3.5">
        {!failed && !done && (
          <span
            aria-hidden
            className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-v2-navy border-t-transparent"
          />
        )}
        {done && <span aria-hidden className="mt-0.5 text-[14px] text-v2-positive">✓</span>}
        {failed && <span aria-hidden className="mt-0.5 text-[14px] text-v2-negative">✕</span>}
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] font-semibold text-v2-text">
            {failed ? `${title} failed` : done ? doneLabel : `${title}…`}
          </div>
          {!failed && !done && (
            <div className="mt-0.5 text-[11.5px] text-v2-muted">
              {[progress, s.phase].filter(Boolean).join(" · ") || "working…"}
              {s.scope && s.scope !== "ALL" ? ` · ${s.scope}` : ""}
            </div>
          )}
          {!failed && !done && (
            <div className="mt-1 text-[10.5px] text-v2-faint">
              Running in the background — you can keep using the app; closing this
              page will not stop it.
            </div>
          )}
          {failed && (
            <div className="mt-0.5 break-words text-[11.5px] text-v2-negative">
              {s.error || "The job failed — check the backend log."}
            </div>
          )}
        </div>
        {(failed || done) && (
          <button
            type="button"
            onClick={job.dismiss}
            aria-label="Dismiss"
            className="shrink-0 rounded-[3px] px-1.5 text-[12px] text-v2-muted hover:bg-v2-header-bg"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
