import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getMLStats, getMLEvaluation } from "../services/api.js";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const DAMAGE_LABELS = ["No Damage", "Minor", "Major", "Destroyed"];
const DAMAGE_KEYS   = ["no_damage", "minor_damage", "major_damage", "destroyed"];

const cellColor = (val, isDiag) => {
  if (isDiag) {
    if (val > 300) return "bg-blue-600 text-white";
    if (val > 100) return "bg-blue-400 text-white";
    return "bg-blue-300 text-white";
  }
  if (!val || val === 0) return "bg-gray-50 text-gray-300";
  return "bg-blue-100 text-blue-800";
};

function pct(n) {
  if (n == null) return "—";
  return (n * 100).toFixed(1) + "%";
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, delta, up }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-gray-600">{label}</p>
        {delta != null && (
          <span className={`text-xs font-semibold flex items-center gap-0.5 ${up ? "text-green-500" : "text-red-500"}`}>
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
              {up ? <path d="M7 14l5-5 5 5z"/> : <path d="M7 10l5 5 5-5z"/>}
            </svg>
            {delta}
          </span>
        )}
      </div>
      <p className="text-3xl font-bold text-gray-900 mb-1">{value}</p>
      <p className="text-xs text-gray-400">{sub}</p>
      <div className="mt-3 h-1 bg-blue-500 rounded-full w-2/3" />
    </div>
  );
}

function PendingCard({ label }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex flex-col justify-between">
      <p className="text-sm text-gray-600 mb-3">{label}</p>
      <div className="space-y-1.5">
        <div className="h-8 bg-gray-100 rounded animate-pulse" />
        <div className="h-3 bg-gray-100 rounded w-2/3 animate-pulse" />
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

const MetricsPage = () => {
  const [stats, setStats]         = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [statsError, setStatsError]     = useState(false);
  const [evalPending, setEvalPending]   = useState(false);
  const [selectedDisaster, setSelectedDisaster] = useState("hurricane-harvey");

  useEffect(() => {
    getMLStats()
      .then(setStats)
      .catch(() => setStatsError(true));

    getMLEvaluation()
      .then(setEvaluation)
      .catch((err) => {
        // 404 / "No evaluation runs" is expected until ML team completes a pass
        setEvalPending(true);
      });
  }, []);

  // ── Distribution chart data ──────────────────────────────────────────────
  const distData = (() => {
    if (!stats) return [];
    const byDisaster = stats.by_disaster ?? {};
    const disasters  = Object.keys(byDisaster);

    return ["no-damage", "minor-damage", "major-damage", "destroyed"].map((key) => {
      const row = { category: key.replace(/-/g, " ").toUpperCase() };
      disasters.forEach((d) => { row[d] = byDisaster[d]?.[key] ?? 0; });
      return row;
    });
  })();

  const disasters = stats ? Object.keys(stats.by_disaster ?? {}) : [];
  const DISASTER_COLORS = ["#3b82f6", "#f97316", "#10b981", "#8b5cf6"];

  // ── KPI cards from evaluation ────────────────────────────────────────────
  const kpis = evaluation ? [
    {
      label: "Model Accuracy",
      value: pct(evaluation.overall_accuracy),
      sub: "Overall correct predictions",
    },
    {
      label: "Macro Precision",
      value: pct(evaluation.macro_precision ?? evaluation.per_class
        ? Object.values(evaluation.per_class).reduce((s, c) => s + (c.precision ?? 0), 0) / Object.keys(evaluation.per_class).length
        : null),
      sub: "Avg across damage classes",
    },
    {
      label: "Macro Recall",
      value: pct(evaluation.macro_recall ?? evaluation.per_class
        ? Object.values(evaluation.per_class).reduce((s, c) => s + (c.recall ?? 0), 0) / Object.keys(evaluation.per_class).length
        : null),
      sub: "Sensitivity metric",
    },
    {
      label: "Macro F1",
      value: evaluation.macro_f1 != null
        ? evaluation.macro_f1.toFixed(3)
        : pct(evaluation.per_class
          ? Object.values(evaluation.per_class).reduce((s, c) => s + (c.f1 ?? 0), 0) / Object.keys(evaluation.per_class).length
          : null),
      sub: "Harmonic mean P/R",
    },
  ] : null;

  // ── Confusion matrix from evaluation ────────────────────────────────────
  const confusionMatrix = evaluation?.confusion_matrix ?? null;
  const matrixLabels = confusionMatrix
    ? (evaluation.class_labels ?? DAMAGE_LABELS.slice(0, confusionMatrix.length))
    : DAMAGE_LABELS;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-8 py-5 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <nav className="text-sm text-gray-400 mb-1 flex gap-1.5 items-center">
              <span className="hover:text-blue-600 cursor-pointer">Home</span>
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
              <span className="hover:text-blue-600 cursor-pointer">Analytics</span>
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
              <span className="text-gray-700">Evaluation &amp; Metrics</span>
            </nav>
            <h1 className="text-2xl font-bold text-gray-900">Evaluation &amp; Metrics</h1>
            <p className="text-sm text-gray-500 mt-1 max-w-xl">
              Comparing VLM damage predictions against ground-truth labels.
            </p>
          </div>
          <button className="flex items-center gap-2 border border-gray-200 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-50 shadow-sm">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
            Export Report
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Summary stats bar */}
        {stats && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4 flex flex-wrap items-center gap-8">
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Total Predictions</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_predictions?.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Disasters</p>
              <p className="text-2xl font-bold text-gray-900">{stats.disasters_count}</p>
            </div>
            {Object.entries(stats.overall_distribution ?? {}).map(([key, val]) => (
              <div key={key}>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">
                  {key.replace(/-/g, " ")}
                </p>
                <p className="text-2xl font-bold text-gray-900">{val?.toLocaleString()}</p>
              </div>
            ))}
            <div className="ml-auto flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              Live data
            </div>
          </div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {evalPending
            ? DAMAGE_LABELS.slice(0, 4).map((l, i) => (
                <PendingCard key={i} label={["Model Accuracy","Macro Precision","Macro Recall","Macro F1"][i]} />
              ))
            : kpis
            ? kpis.map((m) => <KpiCard key={m.label} {...m} />)
            : Array(4).fill(null).map((_, i) => (
                <PendingCard key={i} label={["Model Accuracy","Macro Precision","Macro Recall","Macro F1"][i]} />
              ))
          }
        </div>

        {evalPending && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm text-blue-700 flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0"><path d="M12 2a10 10 0 100 20A10 10 0 0012 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
            Evaluation metrics will appear here once the ML team completes an evaluation pass.
          </div>
        )}

        {/* Charts row */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
          {/* Confusion Matrix */}
          <div className="xl:col-span-3 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Confusion Matrix</h3>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-100 rounded-sm inline-block border border-gray-200"/>Off-diagonal</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-600 rounded-sm inline-block"/>Correct</span>
              </div>
            </div>

            {evalPending || !confusionMatrix ? (
              <div className="flex items-center justify-center h-48 text-sm text-gray-400">
                {evalPending
                  ? "Awaiting ML evaluation run…"
                  : <div className="space-y-2 w-full">
                      {Array(4).fill(null).map((_, i) => (
                        <div key={i} className="flex gap-1">
                          {Array(4).fill(null).map((_, j) => (
                            <div key={j} className="flex-1 h-12 bg-gray-100 rounded animate-pulse" />
                          ))}
                        </div>
                      ))}
                    </div>
                }
              </div>
            ) : (
              <div className="flex">
                <div className="flex items-center mr-2">
                  <p className="text-xs text-gray-400 whitespace-nowrap" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
                    TRUE LABEL (GROUND TRUTH)
                  </p>
                </div>
                <div className="flex-1">
                  <div className="flex mb-1 ml-16">
                    {matrixLabels.map((l) => (
                      <div key={l} className="flex-1 text-center text-xs text-gray-400 font-medium">{l}</div>
                    ))}
                  </div>
                  {confusionMatrix.map((row, ri) => (
                    <div key={ri} className="flex items-center mb-1">
                      <div className="w-16 text-xs text-gray-400 font-medium text-right pr-2">{matrixLabels[ri]}</div>
                      {row.map((val, ci) => (
                        <div
                          key={ci}
                          className={`flex-1 aspect-square flex items-center justify-center text-sm font-bold rounded mx-0.5 ${cellColor(val, ri === ci)}`}
                          style={{ minHeight: 52 }}
                        >
                          {val}
                        </div>
                      ))}
                    </div>
                  ))}
                  <p className="text-center text-xs text-gray-400 font-semibold mt-2 tracking-widest uppercase">Predicted Label (AI)</p>
                </div>
              </div>
            )}
          </div>

          {/* Distribution chart */}
          <div className="xl:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-start justify-between mb-4">
              <h3 className="font-semibold text-gray-900 leading-tight">Distribution by<br/>Severity</h3>
              <div className="flex flex-col gap-1 text-xs text-gray-500">
                {disasters.map((d, i) => (
                  <span key={d} className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-sm inline-block" style={{ background: DISASTER_COLORS[i % DISASTER_COLORS.length] }} />
                    {d.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                ))}
              </div>
            </div>
            <div className="h-52">
              {statsError ? (
                <div className="flex items-center justify-center h-full text-sm text-gray-400">
                  Failed to load stats
                </div>
              ) : !stats ? (
                <div className="flex items-center justify-center h-full">
                  <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={distData} barCategoryGap="25%" barGap={2} margin={{ top: 0, right: 0, bottom: 0, left: -25 }}>
                    <XAxis dataKey="category" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
                    <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}/>
                    {disasters.map((d, i) => (
                      <Bar
                        key={d}
                        dataKey={d}
                        fill={DISASTER_COLORS[i % DISASTER_COLORS.length]}
                        radius={[3, 3, 0, 0]}
                        name={d.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>

        {/* Per-class breakdown table — shown when evaluation data is available */}
        {evaluation?.per_class && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Per-Class Metrics</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                    <th className="text-left py-2 pr-4">Class</th>
                    <th className="text-right py-2 px-4">Precision</th>
                    <th className="text-right py-2 px-4">Recall</th>
                    <th className="text-right py-2 px-4">F1</th>
                    <th className="text-right py-2 pl-4">Support</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(evaluation.per_class).map(([cls, m]) => (
                    <tr key={cls} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2.5 pr-4 font-medium text-gray-800 capitalize">{cls.replace(/_/g, " ")}</td>
                      <td className="text-right py-2.5 px-4 text-gray-600">{pct(m.precision)}</td>
                      <td className="text-right py-2.5 px-4 text-gray-600">{pct(m.recall)}</td>
                      <td className="text-right py-2.5 px-4 text-gray-600">{pct(m.f1)}</td>
                      <td className="text-right py-2.5 pl-4 text-gray-500">{m.support ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricsPage;
