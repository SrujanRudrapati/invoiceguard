import { useCallback, useEffect, useState } from "react";
import { api, type Edits, type QueueItem, type Status } from "../api";

export type Action = "approve" | "reject";
type Lists = Record<Status, QueueItem[]>;
type Notify = (text: string, tone?: "info" | "error") => void;

const STATUSES: Status[] = ["review", "approve", "reject"];
const EMPTY: Lists = { review: [], approve: [], reject: [] };

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected error";
}

function insertAt(items: QueueItem[], index: number, item: QueueItem): QueueItem[] {
  return [...items.slice(0, index), item, ...items.slice(index)];
}

/** Queue lists per status, the open document, and optimistic decisions with rollback. */
export function useReviewQueue(notify: Notify, onDecided: (docId: string) => void) {
  const [lists, setLists] = useState<Lists>(EMPTY);
  const [filter, setFilter] = useState<Status>("review");
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all(STATUSES.map((s) => api.queue(s)))
      .then(([review, approve, reject]) => {
        setLists({ review, approve, reject });
        setCurrentId(review[0]?.doc_id ?? null);
      })
      .catch((error: unknown) => setLoadError(errorText(error)));
  }, []);

  const items = lists[filter];

  const changeFilter = (status: Status) => {
    setFilter(status);
    setCurrentId(lists[status][0]?.doc_id ?? null);
  };

  const step = (delta: number) => {
    const index = items.findIndex((i) => i.doc_id === currentId);
    const next = items[Math.min(Math.max(index + delta, 0), items.length - 1)];
    if (next) setCurrentId(next.doc_id);
  };

  const decide = useCallback(
    (docId: string, action: Action, edits: Edits) => {
      const index = lists.review.findIndex((i) => i.doc_id === docId);
      if (index < 0) return;
      const item = lists.review[index];
      const target: Status = action === "reject" ? "reject" : "approve";
      const hasEdits = Object.keys(edits).length > 0;
      const reviewAction = action === "reject" ? "reject" : hasEdits ? "save_and_approve" : "approve";
      const moved: QueueItem = { ...item, status: target, review_action: reviewAction };
      const next = lists.review[index + 1] ?? lists.review[index - 1] ?? null;

      setLists((l) => ({
        ...l,
        review: l.review.filter((i) => i.doc_id !== docId),
        [target]: [moved, ...l[target].filter((i) => i.doc_id !== docId)],
      }));
      if (filter === "review") setCurrentId(next?.doc_id ?? null);
      notify(action === "reject" ? "Rejected" : "Approved");

      const request = action === "reject" ? api.reject(docId) : api.approve(docId, edits);
      request
        .then((result) => {
          if (result.added_to_eval_set) notify("Approved. Added to eval set");
          onDecided(docId);
        })
        .catch((error: unknown) => {
          setLists((l) => ({
            ...l,
            [target]: l[target].filter((i) => i.doc_id !== docId),
            review: insertAt(l.review.filter((i) => i.doc_id !== docId), index, item),
          }));
          setCurrentId(docId);
          notify(`Not saved: ${errorText(error)}`, "error");
        });
    },
    [lists, filter, notify, onDecided],
  );

  const counts = { review: lists.review.length, approve: lists.approve.length, reject: lists.reject.length };
  return { filter, items, counts, currentId, loadError, setCurrentId, changeFilter, step, decide };
}
