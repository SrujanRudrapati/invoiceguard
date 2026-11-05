export type Status = "review" | "approve" | "reject";

export interface QueueItem {
  doc_id: string;
  status: Status;
  review_action: string | null;
  vendor: string | null;
  total: string | null;
  currency: string | null;
  reasons: string[];
}

export interface Box {
  page: number;
  x0: number;
  top: number;
  x1: number;
  bottom: number;
}

export interface FieldView {
  name: string;
  label: string;
  kind: "money" | "date" | "text";
  value: string | null;
  evidence: string | null;
  boxes: Box[];
  verified: boolean | null;
  note: string | null;
}

export interface LineItem {
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
}

export interface RuleResult {
  name: string;
  passed: boolean;
  failures: string[];
}

export interface AuditEntry {
  action: string;
  entity: string;
  at: string;
  detail: Record<string, unknown>;
}

export interface DocDetail {
  doc_id: string;
  status: Status;
  route: Status;
  review_action: string | null;
  model: string;
  escalated: boolean;
  doc_type: string;
  currency: string | null;
  reasons: string[];
  page_sizes: [number, number][];
  fields: FieldView[];
  line_items: LineItem[];
  rules: RuleResult[];
  audit: AuditEntry[];
}

export interface Decision {
  review_id: number;
  action: string;
  added_to_eval_set: boolean;
}

export interface HistoryRow {
  timestamp: string;
  tag: string;
  system: string;
  set?: string;
  field_acc: number | null;
  review_recall: number | null;
  auto_approve: number | null;
  usd_per_doc: number | null;
  [key: string]: unknown;
}

export interface Evals {
  latest_tag: string | null;
  latest: HistoryRow[];
  history: HistoryRow[];
}

export type Edits = Record<string, string | null>;

export interface SystemStatus {
  systems: string[];
  mocked: boolean;
  mocked_label: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  queue: (status: Status) => request<QueueItem[]>(`/queue?status=${status}`),
  doc: (id: string) => request<DocDetail>(`/docs/${encodeURIComponent(id)}`),
  pdfUrl: (id: string) => `/api/docs/${encodeURIComponent(id)}/pdf`,
  approve: (id: string, edits: Edits) =>
    request<Decision>(`/docs/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ edits }),
    }),
  reject: (id: string) =>
    request<Decision>(`/docs/${encodeURIComponent(id)}/reject`, { method: "POST" }),
  evals: () => request<Evals>("/evals"),
  systemStatus: () => request<SystemStatus>("/status"),
};
