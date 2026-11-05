import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { ReviewDesk } from "./review/ReviewDesk";
import { api } from "./api";
import { Toast, type ToastMessage } from "./Toast";

type Page = "review" | "evals";
const TOAST_MS = 2400;
// Recharts only loads when the Evals page opens.
const EvalsPage = lazy(() => import("./evals/EvalsPage").then((m) => ({ default: m.EvalsPage })));

function pageFromHash(): Page {
  return window.location.hash === "#/evals" ? "evals" : "review";
}

export function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const [mockedLabel, setMockedLabel] = useState<string | null>(null);

  useEffect(() => {
    api
      .systemStatus()
      .then((s) => setMockedLabel(s.mocked ? s.mocked_label : null))
      .catch(() => setMockedLabel(null)); // the desk shows its own API error
  }, []);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), TOAST_MS);
    return () => clearTimeout(id);
  }, [toast]);

  const notify = useCallback((text: string, tone: "info" | "error" = "info") => {
    setToast({ id: Date.now(), text, tone });
  }, []);

  const link = (target: Page, label: string) => (
    <a
      href={target === "evals" ? "#/evals" : "#/"}
      aria-current={page === target ? "page" : undefined}
      className={`px-3 py-1 text-body ${page === target ? "font-medium text-ink" : "text-ink-muted"}`}
    >
      {label}
    </a>
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 shrink-0 items-center border-b border-rule bg-surface px-5">
        <span className="text-body font-semibold">InvoiceGuard</span>
        {mockedLabel && (
          <span className="ml-3 rounded bg-review-tint px-2 py-0.5 text-meta text-review-deep">
            Demo data: {mockedLabel}
          </span>
        )}
        <nav aria-label="Main" className="ml-auto flex">
          {link("review", "Review")}
          {link("evals", "Evals")}
        </nav>
      </header>
      <div className="min-h-0 flex-1">
        {page === "review" ? (
          <ReviewDesk notify={notify} />
        ) : (
          <Suspense fallback={<p className="p-8 text-body text-ink-muted">Loading evals</p>}>
            <EvalsPage />
          </Suspense>
        )}
      </div>
      <Toast message={toast} />
    </div>
  );
}
