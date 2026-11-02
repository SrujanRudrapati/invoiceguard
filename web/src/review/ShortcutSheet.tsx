import { useEffect, useRef } from "react";

const SHORTCUTS: [string, string][] = [
  ["J / K", "Next or previous field"],
  ["Enter", "Edit the selected field, or keep the edit"],
  ["Esc", "Cancel the edit"],
  ["A", "Approve"],
  ["S", "Save edits and approve"],
  ["R", "Reject"],
  ["Up / Down", "Previous or next document"],
  ["?", "Show or hide this sheet"],
];

export function ShortcutSheet({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => dialogRef.current?.focus(), []);
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30" onClick={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="w-96 rounded border border-rule bg-surface p-5"
      >
        <h2 id="shortcuts-title" className="text-title font-semibold">Keyboard shortcuts</h2>
        <dl className="mt-3 grid grid-cols-[96px_1fr] gap-y-2 text-body">
          {SHORTCUTS.map(([keys, action]) => (
            <div key={keys} className="contents">
              <dt className="font-medium">{keys}</dt>
              <dd className="text-ink-muted">{action}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-meta text-ink-muted">Press Esc or ? to close.</p>
      </div>
    </div>
  );
}
