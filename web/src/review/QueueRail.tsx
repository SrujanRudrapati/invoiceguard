import { AnimatePresence, motion } from "framer-motion";
import type { QueueItem, Status } from "../api";
import { decisionLabel, money } from "../format";

type Props = {
  filter: Status;
  counts: Record<Status, number>;
  items: QueueItem[];
  currentId: string | null;
  onFilter: (status: Status) => void;
  onOpen: (docId: string) => void;
};

const FILTERS: { status: Status; label: string }[] = [
  { status: "review", label: "Review" },
  { status: "approve", label: "Approved" },
  { status: "reject", label: "Rejected" },
];

function secondLine(item: QueueItem): string {
  if (item.status !== "review") return decisionLabel(item.status, item.review_action);
  const [first, ...rest] = item.reasons;
  return rest.length ? `${first} (+${rest.length} more)` : (first ?? "");
}

export function QueueRail({ filter, counts, items, currentId, onFilter, onOpen }: Props) {
  return (
    <nav aria-label="Documents" className="flex h-full flex-col border-r border-rule bg-surface">
      <div role="tablist" aria-label="Filter documents" className="flex border-b border-rule">
        {FILTERS.map(({ status, label }) => (
          <button
            key={status}
            role="tab"
            aria-selected={filter === status}
            onClick={() => onFilter(status)}
            className={`flex-1 whitespace-nowrap border-b-2 px-1 py-2.5 text-meta ${
              filter === status
                ? "border-ink font-medium text-ink"
                : "border-transparent text-ink-muted"
            }`}
          >
            {label} <span className="tabular-nums">{counts[status]}</span>
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <p className="px-4 py-6 text-meta text-ink-muted">
          {filter === "review"
            ? "Queue is clear. New invoices appear here after processing."
            : "Nothing here yet."}
        </p>
      ) : (
        <ul className="flex-1 overflow-y-auto">
          <AnimatePresence initial={false}>
            {items.map((item) => {
              const isCurrent = item.doc_id === currentId;
              return (
                <motion.li
                  key={item.doc_id}
                  layout
                  exit={{ opacity: 0, x: -24 }}
                  transition={{ duration: 0.2 }}
                  className="border-b border-rule"
                >
                  <button
                    onClick={() => onOpen(item.doc_id)}
                    aria-current={isCurrent ? "true" : undefined}
                    className={`block w-full border-l-[3px] px-4 py-3 text-left ${
                      isCurrent ? "border-ledger-deep bg-ledger-tint" : "border-transparent"
                    }`}
                  >
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-body font-medium">
                        {item.vendor ?? item.doc_id}
                      </span>
                      <span className="money shrink-0 text-body">
                        {money(item.total, item.currency)}
                      </span>
                    </span>
                    <span
                      className={`mt-0.5 block truncate text-meta ${
                        item.status === "review" ? "text-review-deep" : "text-ink-muted"
                      }`}
                    >
                      {secondLine(item)}
                    </span>
                  </button>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </nav>
  );
}
