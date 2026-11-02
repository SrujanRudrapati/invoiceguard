import { motion } from "framer-motion";
import type { Ref } from "react";
import type { DocDetail, Edits, FieldView } from "../api";
import { decisionLabel, money, shortTime } from "../format";

type Props = {
  detail: DocDetail;
  fieldIndex: number;
  isEditing: boolean;
  draft: string;
  edits: Edits;
  isReadOnly: boolean;
  selectedRowRef: Ref<HTMLLIElement>;
  panelRef: Ref<HTMLDivElement>;
  onSelect: (index: number) => void;
  onDraftChange: (value: string) => void;
  onCommit: () => void;
  onCancel: () => void;
};

const PLACEHOLDER = { money: "4812.50", date: "2026-12-01", text: "" } as const;

function display(field: FieldView, value: string | null, currency: string | null): string {
  if (value === null) return "Not on the document";
  return field.kind === "money" ? money(value, currency) : value;
}

function FieldNote({ field, edited }: { field: FieldView; edited: boolean }) {
  if (edited) {
    const text = field.value === null
      ? "Edited. Nothing was extracted here."
      : `Edited. Extracted value was ${field.value}.`;
    return <p className="text-meta text-ledger-deep">{text}</p>;
  }
  if (field.value !== null && field.verified === false) {
    return <p className="text-meta text-review-deep">{field.note}</p>;
  }
  if (field.evidence) {
    return <p className="truncate text-meta text-ledger-deep">“{field.evidence}”</p>;
  }
  return null;
}

function auditText(action: string, entity: string, detail: Record<string, unknown>): string {
  if (entity === "document") return "Received";
  if (entity === "extraction") return `Routed to ${String(detail.route)}`;
  if (entity === "eval_set") return "Added to eval set";
  if (action === "save_and_approve") return "Edited and approved by reviewer";
  if (action === "approve") return "Approved by reviewer";
  if (action === "reject") return "Rejected by reviewer";
  return action;
}

export function FieldsPanel(props: Props) {
  const { detail, fieldIndex, isEditing, draft, edits, isReadOnly } = props;
  const vendor = detail.fields.find((f) => f.name === "vendor_name")?.value ?? detail.doc_id;
  const statusText = decisionLabel(detail.status, detail.review_action);

  return (
    <div
      ref={props.panelRef}
      className="h-full overflow-y-auto bg-surface pb-[var(--bottom-bar-height)] scroll-pb-[var(--bottom-bar-height)]"
    >
      <header className="border-b border-rule px-5 py-4">
        <h2 className="text-title font-semibold">{vendor}</h2>
        <p className="mt-1 text-meta text-ink-muted">
          {statusText}. Read by {detail.model}
          {detail.escalated ? " after Haiku's reading could not be verified" : ""}
        </p>
        {detail.status === "review" && detail.reasons.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2" aria-label="Why this needs review">
            {detail.reasons.map((reason) => (
              <li key={reason} className="rounded bg-review-tint px-2 py-1 text-meta text-review-deep">
                {reason}
              </li>
            ))}
          </ul>
        )}
      </header>

      <ul role="listbox" aria-label="Fields" className="border-b border-rule">
        {detail.fields.map((field, index) => {
          const isSelected = index === fieldIndex;
          const edited = field.name in edits;
          const value = edited ? edits[field.name] : field.value;
          return (
            <li
              key={field.name}
              ref={isSelected ? props.selectedRowRef : undefined}
              role="option"
              aria-selected={isSelected}
              onClick={() => props.onSelect(index)}
              className={`cursor-pointer border-l-2 px-5 py-2.5 ${
                isSelected ? "border-ledger-deep bg-ledger-tint" : "border-transparent"
              }`}
            >
              <div className="flex items-baseline justify-between gap-4">
                <span className="shrink-0 text-meta text-ink-muted">{field.label}</span>
                {isSelected && isEditing && !isReadOnly ? (
                  <motion.input
                    initial={{ opacity: 0.4 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.12 }}
                    autoFocus
                    aria-label={`Edit ${field.label.toLowerCase()}`}
                    value={draft}
                    placeholder={PLACEHOLDER[field.kind]}
                    onChange={(e) => props.onDraftChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") props.onCommit();
                      if (e.key === "Escape") props.onCancel();
                      e.stopPropagation();
                    }}
                    className={`w-44 rounded border border-ledger-deep bg-surface px-2 py-0.5 text-body ${
                      field.kind === "money" ? "money" : ""
                    }`}
                  />
                ) : (
                  <span
                    className={`text-body ${field.kind === "money" ? "money" : ""} ${
                      value === null ? "text-ink-muted" : ""
                    }`}
                  >
                    {display(field, value, detail.currency)}
                  </span>
                )}
              </div>
              <FieldNote field={field} edited={edited} />
            </li>
          );
        })}
      </ul>

      {detail.line_items.length > 0 && (
        <section className="border-b border-rule px-5 py-4" aria-labelledby="line-items">
          <h3 id="line-items" className="text-body font-medium">Line items</h3>
          <table className="mt-2 w-full text-meta">
            <tbody>
              {detail.line_items.map((item, n) => (
                <tr key={n} className="align-top">
                  <td className="py-1 pr-3">{item.description}</td>
                  <td className="money py-1 pr-3 text-ink-muted">{Number(item.quantity)}</td>
                  <td className="money py-1">{money(item.amount, detail.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {detail.rules.length > 0 && (
        <section className="border-b border-rule px-5 py-4" aria-labelledby="rule-checks">
          <h3 id="rule-checks" className="text-body font-medium">Rule checks</h3>
          <ul className="mt-2 space-y-1.5">
            {detail.rules.map((rule) => (
              <li key={rule.name} className="text-meta">
                <span className="flex justify-between gap-3">
                  <span>{rule.name}</span>
                  <span className={rule.passed ? "text-approve" : "text-review-deep"}>
                    {rule.passed ? "Passed" : "Failed"}
                  </span>
                </span>
                {rule.failures.map((f) => (
                  <span key={f} className="block text-review-deep">{f}</span>
                ))}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="px-5 py-4" aria-labelledby="history">
        <h3 id="history" className="text-body font-medium">History</h3>
        <ol className="mt-2 space-y-1">
          {detail.audit.map((entry, n) => (
            <li key={n} className="flex justify-between gap-3 text-meta">
              <span>{auditText(entry.action, entry.entity, entry.detail)}</span>
              <span className="text-ink-muted">{shortTime(entry.at)}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
