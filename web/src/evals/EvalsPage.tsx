import { useEffect, useState } from "react";
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Evals, type HistoryRow } from "../api";

const SYSTEMS = [
  { key: "baseline", label: "Regex", color: "#56647a" },
  { key: "haiku", label: "Haiku", color: "#7f9dbf" },
  { key: "sonnet", label: "Sonnet", color: "#1e2b3c" },
  { key: "cascade", label: "Cascade", color: "#3e5e82" },
];
// Replay re-scores recorded answers, so it shares a table row but never a chart point.
const TABLE_SYSTEMS = [...SYSTEMS, { key: "replay", label: "Replay (recorded, mocked)", color: "#56647a" }];
const FREE_FLOOR = 0.000001; // log axes cannot show $0
const AXIS = { fontSize: 13, fill: "#56647a" };

const setOf = (row: HistoryRow) => row.set ?? "main";
const pct = (v: unknown) => (typeof v === "number" ? v.toFixed(3) : "n/a");
const usd = (v: unknown) =>
  typeof v !== "number" ? "n/a" : v === 0 ? "$0" : `$${v.toPrecision(2)}`;
const COST_TICKS = [0.000001, 0.00001, 0.0001, 0.001, 0.01];
const tickUsd = (v: number) => `$${v}`;

/** One point per system; systems at the same spot (within 10% cost) share one label. */
function costRecallPoints(latest: HistoryRow[]) {
  const raw = SYSTEMS.flatMap((s) => {
    const row = latest.find((r) => r.system === s.key && setOf(r) === "main");
    if (!row || row.review_recall === null) return [];
    return [{ ...s, x: Math.max(row.usd_per_doc ?? 0, FREE_FLOOR), y: row.review_recall }];
  });
  const near = (a: (typeof raw)[0], b: (typeof raw)[0]) =>
    a.y === b.y && Math.abs(a.x - b.x) / Math.max(a.x, b.x) < 0.1;
  return raw.map((p, i) => {
    const group = raw.filter((q) => near(p, q));
    const isFirst = raw.findIndex((q) => near(p, q)) === i;
    return { ...p, label: isFirst ? group.map((q) => q.label).join(" and ") : "" };
  });
}

function accuracyByTag(history: HistoryRow[]) {
  const tags = [...new Set(history.filter((r) => setOf(r) === "main" && r.tag).map((r) => r.tag))];
  return tags.map((tag) => {
    const point: Record<string, string | number | null> = { tag };
    for (const s of SYSTEMS) {
      const rows = history.filter((r) => r.tag === tag && r.system === s.key && setOf(r) === "main");
      point[s.key] = rows.at(-1)?.field_acc ?? null;
    }
    return point;
  });
}

function ResultsTable({ rows, title }: { rows: HistoryRow[]; title: string }) {
  if (rows.length === 0) return null;
  return (
    <section className="mt-8">
      <h2 className="text-title font-semibold">{title}</h2>
      <table className="mt-3 w-full border-t border-rule text-body">
        <thead className="text-meta text-ink-muted">
          <tr className="border-b border-rule">
            <th className="py-2 text-left font-normal">System</th>
            <th className="py-2 text-left font-normal">Tag</th>
            <th className="money py-2 font-normal">Field accuracy</th>
            <th className="money py-2 font-normal">Review recall</th>
            <th className="money py-2 font-normal">Auto-approve</th>
            <th className="money py-2 font-normal">Verified but wrong</th>
            <th className="money py-2 font-normal">Escalated</th>
            <th className="money py-2 font-normal">Cost per doc</th>
            <th className="money py-2 font-normal">Median latency</th>
          </tr>
        </thead>
        <tbody>
          {TABLE_SYSTEMS.map((s) => {
            const r = rows.find((row) => row.system === s.key);
            if (!r) return null;
            return (
              <tr key={s.key} className="border-b border-rule">
                <td className="py-2">{s.label}</td>
                <td className="py-2 text-ink-muted">{r.tag}</td>
                <td className="money py-2">{pct(r.field_acc)}</td>
                <td className="money py-2">{pct(r.review_recall)}</td>
                <td className="money py-2">{pct(r.auto_approve)}</td>
                <td className="money py-2">{String(r.verified_wrong ?? "n/a")}</td>
                <td className="money py-2">{pct(r.escalation_rate)}</td>
                <td className="money py-2">{usd(r.usd_per_doc)}</td>
                <td className="money py-2">{`${Math.round(Number(r.p50_ms))} ms`}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export function EvalsPage() {
  const [evals, setEvals] = useState<Evals | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.evals().then(setEvals).catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed"));
  }, []);

  if (error) return <p className="p-8 text-body text-reject">Could not load evals: {error}</p>;
  if (!evals) return <p className="p-8 text-body text-ink-muted">Loading evals</p>;
  if (!evals.latest_tag) return <p className="p-8 text-body">No eval runs yet. Run make eval.</p>;

  const points = costRecallPoints(evals.latest);
  const trend = accuracyByTag(evals.history);
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-8 py-8">
        <h1 className="text-display font-semibold">Evals</h1>
        <p className="mt-1 text-meta text-ink-muted">
          Newest tagged result for each system (tag in the table), main set of 24 documents
          unless noted.
        </p>

        <div className="mt-8 grid grid-cols-2 gap-10 max-lg:grid-cols-1">
          <figure>
            <figcaption className="text-body font-medium">Cost per document against review recall</figcaption>
            <div className="mt-3 h-64 border-t border-rule">
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 16, right: 64, bottom: 8, left: 0 }}>
                  <CartesianGrid stroke="#d5ded7" strokeDasharray="0" />
                  <XAxis type="number" dataKey="x" scale="log" domain={[FREE_FLOOR, 0.05]}
                    ticks={COST_TICKS} tickFormatter={tickUsd} tick={AXIS} />
                  <YAxis type="number" dataKey="y" domain={[0, 1]} tick={AXIS} width={40} />
                  <Tooltip formatter={(v) => (typeof v === "number" ? v.toPrecision(3) : String(v))} />
                  {points.map((p) => (
                    <Scatter key={p.key} data={[p]} fill={p.color}>
                      <LabelList dataKey="label" position="bottom" offset={10} fill={p.color} fontSize={13} />
                    </Scatter>
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-meta text-ink-muted">
              Log scale. Regex costs $0 and is drawn at $0.000001 so it fits.
            </p>
          </figure>

          <figure>
            <figcaption className="text-body font-medium">Field accuracy by run</figcaption>
            <div className="mt-3 h-64 border-t border-rule">
              <ResponsiveContainer>
                <LineChart data={trend} margin={{ top: 16, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid stroke="#d5ded7" />
                  <XAxis dataKey="tag" tick={AXIS} />
                  <YAxis domain={[0.8, 1]} tick={AXIS} width={40} />
                  <Tooltip />
                  {SYSTEMS.map((s) => (
                    <Line key={s.key} dataKey={s.key} name={s.label} stroke={s.color}
                      strokeWidth={2} dot={{ r: 3 }} connectNulls isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 flex flex-wrap gap-4 text-meta">
              {SYSTEMS.map((s) => (
                <span key={s.key} style={{ color: s.color }}>{s.label}</span>
              ))}
            </p>
          </figure>
        </div>

        <ResultsTable title="Main set" rows={evals.latest.filter((r) => setOf(r) === "main")} />
        <ResultsTable title="Hard set (6 documents)" rows={evals.latest.filter((r) => setOf(r) === "hard")} />
      </div>
    </div>
  );
}
