"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { formatEntity } from "@/lib/utils";

/**
 * App-wide entity id → real name resolution (item 3). Fetches the flat
 * /hierarchy/entity-names map ONCE (module-level cache shared across every
 * component) so any place holding only an id can render "ID · Name" via a
 * single shared helper instead of ad-hoc per-page lookups.
 */
let _cache: Record<string, string> | null = null;
let _inflight: Promise<Record<string, string>> | null = null;

async function loadNames(): Promise<Record<string, string>> {
  if (_cache) return _cache;
  if (!_inflight) {
    _inflight = apiClient
      .get<{ names: Record<string, string> }>("/hierarchy/entity-names")
      .then((d) => (_cache = d.names ?? {}))
      .catch(() => (_cache = {}));
  }
  return _inflight;
}

export function useEntityLabel() {
  const [names, setNames] = useState<Record<string, string>>(_cache ?? {});
  useEffect(() => {
    if (_cache) return;
    let alive = true;
    void loadNames().then((m) => alive && setNames(m));
    return () => {
      alive = false;
    };
  }, []);
  // label(id) -> "ID · Name"; nameOf(id) -> just the name (or id if unknown).
  return {
    label: (id: string | null | undefined) => formatEntity(id, id ? names[id] : undefined),
    nameOf: (id: string | null | undefined) => (id ? names[id] || id : "—"),
    ready: Object.keys(names).length > 0,
  };
}
