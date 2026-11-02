import type { DocDetail } from "../api";
import { decisionLabel } from "../format";

type Props = {
  detail: DocDetail | null;
  hasEdits: boolean;
  onApprove: () => void;
  onSaveAndApprove: () => void;
  onReject: () => void;
  onShortcuts: () => void;
};

const KEY = "ml-1.5 rounded border border-current/30 px-1 text-meta";

export function BottomBar({ detail, hasEdits, onApprove, onSaveAndApprove, onReject, onShortcuts }: Props) {
  const isReview = detail?.status === "review";
  return (
    <footer className="flex h-[var(--bottom-bar-height)] shrink-0 items-center gap-3 border-t border-rule bg-surface px-5">
      {isReview ? (
        <>
          <button
            onClick={onApprove}
            disabled={hasEdits}
            className="rounded bg-approve px-3.5 py-1.5 text-body font-medium text-white disabled:opacity-40"
          >
            Approve <kbd className={KEY}>A</kbd>
          </button>
          <button
            onClick={onSaveAndApprove}
            className="rounded border border-approve px-3.5 py-1.5 text-body font-medium text-approve"
          >
            Save and approve <kbd className={KEY}>S</kbd>
          </button>
          <button
            onClick={onReject}
            className="rounded border border-reject px-3.5 py-1.5 text-body font-medium text-reject"
          >
            Reject <kbd className={KEY}>R</kbd>
          </button>
          {hasEdits && (
            <span className="text-meta text-ink-muted">Edits pending. Save and approve to keep them.</span>
          )}
        </>
      ) : (
        <span className="text-meta text-ink-muted">
          {detail ? `${decisionLabel(detail.status, detail.review_action)}. Read-only.` : ""}
        </span>
      )}
      <button onClick={onShortcuts} className="ml-auto px-2 py-1.5 text-body text-ink-muted">
        Shortcuts <kbd className={KEY}>?</kbd>
      </button>
    </footer>
  );
}
