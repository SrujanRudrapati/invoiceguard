import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DocDetail } from "../api";

/** Fetches and caches document details; `invalidate` forces a refetch after a decision. */
export function useDocDetail(docId: string | null) {
  const cache = useRef(new Map<string, DocDetail>());
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!docId) return setDetail(null);
    const cached = cache.current.get(docId);
    if (cached) return setDetail(cached);
    let isStale = false;
    setError(null);
    api
      .doc(docId)
      .then((d) => {
        cache.current.set(docId, d);
        if (!isStale) setDetail(d);
      })
      .catch((e: unknown) => !isStale && setError(e instanceof Error ? e.message : "Could not load"));
    return () => {
      isStale = true;
    };
  }, [docId, version]);

  const invalidate = useCallback((id: string) => {
    cache.current.delete(id);
    setVersion((v) => v + 1);
  }, []);

  return { detail: detail?.doc_id === docId ? detail : null, error, invalidate };
}
