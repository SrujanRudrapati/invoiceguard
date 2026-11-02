import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DocDetail, Edits } from "../api";
import { BottomBar } from "./BottomBar";
import { Connector } from "./Connector";
import { FieldsPanel } from "./FieldsPanel";
import { PdfPane } from "./PdfPane";
import { QueueRail } from "./QueueRail";
import { ShortcutSheet } from "./ShortcutSheet";
import { useDocDetail } from "./useDocDetail";
import { useReviewQueue } from "./useReviewQueue";

type Notify = (text: string, tone?: "info" | "error") => void;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Review docs open on the first field that needs attention; others on the total. */
function defaultFieldIndex(detail: DocDetail): number {
  const needsLook = detail.fields.findIndex(
    (f) => f.verified === false || (f.value === null && f.name !== "po_number"),
  );
  if (detail.status === "review" && needsLook >= 0) return needsLook;
  return Math.max(detail.fields.findIndex((f) => f.name === "total"), 0);
}

function editProblem(kind: string, label: string, value: string): string | null {
  if (!value) return null;
  if (kind === "money" && Number.isNaN(Number(value.replace(/,/g, "")))) {
    return `${label} must be a number like 4812.50`;
  }
  if (kind === "date" && !ISO_DATE.test(value)) return `${label} must be a date like 2026-12-01`;
  return null;
}

export function ReviewDesk({ notify }: { notify: Notify }) {
  const [edits, setEdits] = useState<Record<string, Edits>>({});
  const [selection, setSelection] = useState<{ docId: string; index: number } | null>(null);
  const [editing, setEditing] = useState<{ docId: string; draft: string } | null>(null);
  const [showSheet, setShowSheet] = useState(false);
  const [rowEl, setRowEl] = useState<HTMLLIElement | null>(null);
  const [highlightEl, setHighlightEl] = useState<HTMLElement | null>(null);
  const [panelEl, setPanelEl] = useState<HTMLDivElement | null>(null);
  const [pdfEl, setPdfEl] = useState<HTMLDivElement | null>(null);
  const [shouldSlide, setShouldSlide] = useState(false);
  const scrollRoots = useMemo(() => [pdfEl, panelEl], [pdfEl, panelEl]);

  const detailRef = useRef<(id: string) => void>(() => {});
  const onDecided = useCallback((id: string) => {
    detailRef.current(id);
    setEdits(({ [id]: _done, ...rest }) => rest);
  }, []);
  const queue = useReviewQueue(notify, onDecided);
  const { detail, error, invalidate } = useDocDetail(queue.currentId);
  useEffect(() => {
    detailRef.current = invalidate;
  }, [invalidate]);

  const docId = detail?.doc_id ?? null;
  const docEdits = (docId && edits[docId]) || {};
  const hasEdits = Object.keys(docEdits).length > 0;
  const isReadOnly = detail?.status !== "review";
  const fieldIndex = detail
    ? selection?.docId === docId ? selection.index : defaultFieldIndex(detail)
    : 0;
  const field = detail?.fields[fieldIndex];
  const isEditing = editing?.docId === docId && editing !== null;

  // Keep the selected field visible in its panel whenever the selection or document changes.
  useEffect(() => {
    rowEl?.scrollIntoView({ block: "nearest" });
  }, [rowEl, fieldIndex, docId]);

  const selectField = (index: number) => {
    if (!detail) return;
    const clamped = Math.min(Math.max(index, 0), detail.fields.length - 1);
    setSelection({ docId: detail.doc_id, index: clamped });
    setEditing(null);
  };

  const startEdit = () => {
    if (!detail || !field || isReadOnly) return;
    const current = field.name in docEdits ? docEdits[field.name] : field.value;
    setEditing({ docId: detail.doc_id, draft: current ?? "" });
  };

  const commitEdit = () => {
    if (!detail || !field || !editing) return;
    const value = editing.draft.trim();
    const problem = editProblem(field.kind, field.label, value);
    if (problem) return notify(problem, "error");
    const { [field.name]: _old, ...others } = docEdits;
    const next = value === (field.value ?? "") ? others : { ...others, [field.name]: value || null };
    setEdits((all) => ({ ...all, [detail.doc_id]: next }));
    setEditing(null);
  };

  const decide = (action: "approve" | "save" | "reject") => {
    if (!detail || isReadOnly) return;
    if (action === "approve" && hasEdits) {
      return notify("Edits pending. Press S to save and approve.", "error");
    }
    setShouldSlide(true);
    setEditing(null);
    queue.decide(detail.doc_id, action === "reject" ? "reject" : "approve",
      action === "save" ? docEdits : {});
  };

  /** Plain navigation never slides; only a decision brings the next doc in with motion. */
  const navigate = (go: () => void) => {
    setShouldSlide(false);
    go();
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    if (showSheet) {
      if (e.key === "Escape" || e.key === "?") setShowSheet(false);
      return;
    }
    if (e.key === "Enter" && tag === "BUTTON") return; // let focused buttons activate
    const handlers: Record<string, () => void> = {
      j: () => selectField(fieldIndex + 1),
      k: () => selectField(fieldIndex - 1),
      Enter: startEdit,
      a: () => decide("approve"),
      s: () => decide("save"),
      r: () => decide("reject"),
      ArrowDown: () => navigate(() => queue.step(1)),
      ArrowUp: () => navigate(() => queue.step(-1)),
      "?": () => setShowSheet(true),
    };
    const handler = handlers[e.key.length === 1 ? e.key.toLowerCase() : e.key] ?? handlers[e.key];
    if (!handler) return;
    e.preventDefault();
    handler();
  };

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const selectionKey = `${docId}:${field?.name}`;

  return (
    <div className="flex h-full flex-col">
      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_360px] grid-rows-[minmax(0,1fr)] overflow-hidden max-xl:grid-cols-[240px_1fr_320px]">
        <QueueRail
          filter={queue.filter}
          counts={queue.counts}
          items={queue.items}
          currentId={queue.currentId}
          onFilter={(status) => navigate(() => queue.changeFilter(status))}
          onOpen={(id) => navigate(() => queue.setCurrentId(id))}
        />
        <main className="min-h-0 min-w-0">
          {queue.loadError && (
            <p className="p-8 text-body text-reject">
              Could not reach the API ({queue.loadError}). Start it with make api.
            </p>
          )}
          {error && <p className="p-8 text-body text-reject">{error}</p>}
          {!queue.currentId && !queue.loadError && (
            <p className="p-8 text-body text-ink-muted">
              {queue.filter === "review"
                ? "Queue is clear. New invoices appear here after processing."
                : "Pick a document from the list."}
            </p>
          )}
          {detail && (
            <motion.div
              key={detail.doc_id}
              className="h-full"
              initial={shouldSlide ? { opacity: 0, x: 24 } : false}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <PdfPane
                docId={detail.doc_id}
                pageSizes={detail.page_sizes}
                boxes={field?.boxes ?? []}
                selectionKey={selectionKey}
                scrollEl={pdfEl}
                onScrollEl={setPdfEl}
                onHighlight={setHighlightEl}
              />
            </motion.div>
          )}
        </main>
        <aside className="min-h-0 border-l border-rule" aria-label="Extracted fields">
          {detail && (
            <FieldsPanel
              detail={detail}
              fieldIndex={fieldIndex}
              isEditing={isEditing}
              draft={editing?.draft ?? ""}
              edits={docEdits}
              isReadOnly={isReadOnly}
              selectedRowRef={setRowEl}
              panelRef={setPanelEl}
              onSelect={selectField}
              onDraftChange={(draft) => docId && setEditing({ docId, draft })}
              onCommit={commitEdit}
              onCancel={() => setEditing(null)}
            />
          )}
        </aside>
      </div>
      <BottomBar
        detail={detail}
        hasEdits={hasEdits}
        onApprove={() => decide("approve")}
        onSaveAndApprove={() => decide("save")}
        onReject={() => decide("reject")}
        onShortcuts={() => setShowSheet(true)}
      />
      {detail && (
        <Connector
          from={rowEl}
          to={highlightEl}
          scrollRoots={scrollRoots}
          animationKey={selectionKey}
        />
      )}
      {showSheet && <ShortcutSheet onClose={() => setShowSheet(false)} />}
    </div>
  );
}
