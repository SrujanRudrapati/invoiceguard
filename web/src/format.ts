const SYMBOLS: Record<string, string> = { USD: "$", EUR: "€", GBP: "£" };

export function money(value: string | null, currency?: string | null): string {
  if (value === null || value === "") return "";
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  const formatted = number.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const symbol = currency ? (SYMBOLS[currency] ?? `${currency} `) : "";
  return number < 0 ? `-${symbol}${formatted.slice(1)}` : `${symbol}${formatted}`;
}

export function shortTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function decisionLabel(status: string, reviewAction: string | null): string {
  if (status === "approve") return reviewAction ? "Approved by reviewer" : "Approved by system";
  if (status === "reject") return reviewAction ? "Rejected by reviewer" : "Rejected by system";
  return "Needs review";
}
