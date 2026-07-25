"use client";
/**
 * Driver display metadata — FIX_SPEC_R8 A. The SINGLE frontend source of
 * driver names, descriptions and computations, fetched once from GQ-004
 * get_driver_causes (phx_dm_v2_driver_cause). Every place a driver name
 * appears (glossary, driver tags, evidence, exports) renders display_name
 * from here — driver names are NEVER hardcoded in components, so the
 * operator can rename a driver by editing the seed / graph with no code
 * change. cause_id is the permanent internal key and is only ever shown as
 * a last-resort fallback while metadata is loading or for an unseeded id.
 */
import { useEffect, useState } from "react";
import { type DriverCause, v2Api } from "@/lib/api/v2";

let cache: DriverCause[] | null = null;
let inflight: Promise<DriverCause[]> | null = null;

export async function fetchDriverCauses(): Promise<DriverCause[]> {
  if (cache) return cache;
  if (!inflight) {
    inflight = v2Api
      .driverCauses()
      .then((res) => {
        // R9 F — glossary order = display_order (attribution order) from
        // phx_dm_v2_driver_cause. A missing/zero order sorts LAST (not first,
        // which would scramble the list ahead of seeded causes); ties break
        // by display name so the order is total and stable. Number() is
        // explicit belt-and-braces: a pre-R8 live graph stores display_order
        // as STRING and "10" must never compare lexicographically before "2".
        const key = (c: DriverCause) => {
          const n = Number(c.display_order);
          return Number.isFinite(n) && n > 0 ? n : Number.MAX_SAFE_INTEGER;
        };
        cache = [...res.causes].sort(
          (a, b) => key(a) - key(b)
            || (a.display_name || a.cause_id).localeCompare(b.display_name || b.cause_id));
        return cache;
      })
      .catch((err) => {
        inflight = null; // allow retry on the next consumer
        throw err;
      });
  }
  return inflight;
}

/** Last-resort readable form of a cause_id (data, not a name literal) —
 * shown only while metadata loads or if an id is unseeded. */
export const humanizeCauseId = (causeId: string) =>
  causeId.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

export interface DriverCauseIndex {
  causes: DriverCause[];
  byId: Record<string, DriverCause>;
  loaded: boolean;
  /** Stored display_name for a cause_id, humanised-id fallback. */
  name: (causeId: string) => string;
}

export function useDriverCauses(): DriverCauseIndex {
  const [causes, setCauses] = useState<DriverCause[]>(cache ?? []);
  useEffect(() => {
    if (cache) return;
    let alive = true;
    fetchDriverCauses()
      .then((rows) => alive && setCauses(rows))
      .catch(() => {
        /* fallback: humanised ids until a retry succeeds */
      });
    return () => {
      alive = false;
    };
  }, []);
  const byId = Object.fromEntries(causes.map((c) => [c.cause_id, c]));
  return {
    causes,
    byId,
    loaded: causes.length > 0,
    name: (causeId: string) => byId[causeId]?.display_name || humanizeCauseId(causeId),
  };
}
