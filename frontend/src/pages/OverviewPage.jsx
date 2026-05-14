import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { getMLStats, getMLJobs } from "../services/api.js";
import Breadcrumb from "../components/Breadcrumb.jsx";

// ─── Constants ────────────────────────────────────────────────────────────────

const DAMAGE_ORDER = ["no-damage", "minor-damage", "major-damage", "destroyed"];
const DAMAGE_META = {
  "no-damage":    { label: "No Damage", color: "#22c55e", barColor: "#22c55e" },
  "minor-damage": { label: "Minor",     color: "#facc15", barColor: "#facc15" },
  "major-damage": { label: "Major",     color: "#f97316", barColor: "#f97316" },
  "destroyed":    { label: "Destroyed", color: "#ef4444", barColor: "#ef4444" },
};

const STATUS_STYLES = {
  completed: { badge: "bg-green-50 text-green-700", dot: "bg-green-500" },
  failed:    { badge: "bg-red-50   text-red-600",   dot: "bg-red-500"   },
  running:   { badge: "bg-blue-50  text-blue-700",  dot: "bg-blue-500 animate-pulse" },
  pending:   { badge: "bg-gray-50  text-gray-500",  dot: "bg-gray-400"  },
};

function fmt(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString();
}

function timeSince(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function Skeleton({ className = "" }) {
  return <div className={`bg-gray-100 rounded animate-pulse ${className}`} />;
}

// ─── KPI Icons (SVG) ─────────────────────────────────────────────────────────

const ICONS = {
  buildings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-blue-600">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 21h18M9 21V7l6-4v18M9 7H5a1 1 0 00-1 1v13M15 21V10.5"/>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 7h.01M12 11h.01M12 15h.01M9 11h.01M9 15h.01"/>
    </svg>
  ),
  destroyed: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-red-500">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
    </svg>
  ),
  disasters: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-orange-500">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064"/>
      <circle cx="12" cy="12" r="9" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  jobs: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-violet-500">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
    </svg>
  ),
};

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, iconKey, loading }) {
  return (
    <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 bg-gray-50 rounded-xl flex items-center justify-center border border-gray-100">
          {ICONS[iconKey]}
        </div>
      </div>
      <p className="text-gray-500 text-xs mb-1">{label}</p>
      {loading
        ? <Skeleton className="h-8 w-24 mt-1" />
        : <p className="text-2xl font-bold text-gray-900">{value}</p>
      }
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const OverviewPage = () => {
  const [stats, setStats]   = useState(null);
  const [jobs, setJobs]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getMLStats().catch(() => null),
      getMLJobs(10).catch(() => null),
    ]).then(([s, j]) => {
      setStats(s);
      setJobs(j?.jobs ?? []);
      setLoading(false);
    });
  }, []);

  // ── Derived values — Harvey only ─────────────────────────────────────────
  const harveyKey = Object.keys(stats?.by_disaster ?? {}).find(k => k.includes("harvey"));
  const dist      = harveyKey ? (stats.by_disaster[harveyKey] ?? {}) : {};
  const total     = Object.values(dist).reduce((s, v) => s + (v ?? 0), 0);
  const destroyed = dist["destroyed"] ?? 0;

  // Structural class percentages — Harvey only
  const structuralBars = DAMAGE_ORDER.map((key) => {
    const count = dist[key] ?? 0;
    const pct   = total > 0 ? Math.round((count / total) * 100) : 0;
    return { key, ...DAMAGE_META[key], count, pct };
  });
  const chartData = harveyKey ? (() => {
    const counts = stats.by_disaster[harveyKey];
    const row = { disaster: "Hurricane Harvey" };
    DAMAGE_ORDER.forEach((k) => { row[k] = counts?.[k] ?? 0; });
    return [row];
  })() : [];

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-100 px-8 py-5 flex-shrink-0">
        <Breadcrumb crumbs={[
          { label: "Home",             page: "landing"  },
          { label: "Dashboard",        page: "overview" },
          { label: "Hurricane Harvey", page: "overview" },
          { label: "Overview" },
        ]} />
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Overview</h1>
        <p className="text-sm text-gray-500 mt-1">
          Hurricane Harvey — damage assessment summary and inference activity.
        </p>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">

        {/* KPI Cards */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          <KpiCard
            iconKey="disasters"
            label="Disaster"
            value={loading ? null : "Hurricane Harvey"}
            sub="2017 · Texas Gulf Coast"
            loading={loading}
          />
          <KpiCard
            iconKey="buildings"
            label="Buildings Assessed"
            value={fmt(total)}
            sub="Total VLM predictions"
            loading={loading}
          />
          <KpiCard
            iconKey="destroyed"
            label="Destroyed"
            value={fmt(destroyed)}
            sub={total > 0 ? `${Math.round((destroyed / total) * 100)}% of total` : undefined}
            loading={loading}
          />
          <KpiCard
            iconKey="jobs"
            label="Inference Jobs"
            value={loading ? null : fmt(jobs?.length ?? 0)}
            sub="Completed model runs"
            loading={loading}
          />
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

          {/* Per-disaster bar chart */}
          <div className="xl:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-start justify-between mb-1">
              <div>
                <h3 className="font-semibold text-gray-900">Damage Distribution by Disaster</h3>
                <p className="text-xs text-gray-400 mt-0.5">Building counts per damage class</p>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                {DAMAGE_ORDER.map((k) => (
                  <span key={k} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: DAMAGE_META[k].barColor }} />
                    {DAMAGE_META[k].label}
                  </span>
                ))}
              </div>
            </div>
            <div className="h-52 mt-2">
              {loading ? (
                <div className="flex items-end gap-3 h-full px-4 pb-4">
                  {[60, 90, 40, 75].map((h, i) => (
                    <div key={i} className="flex-1 bg-gray-100 rounded animate-pulse" style={{ height: `${h}%` }} />
                  ))}
                </div>
              ) : chartData.length === 0 ? (
                <div className="flex items-center justify-center h-full text-sm text-gray-400">
                  No data available
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} barCategoryGap="30%" barGap={2} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                    <XAxis dataKey="disaster" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
                      formatter={(val, name) => [val.toLocaleString(), DAMAGE_META[name]?.label ?? name]}
                    />
                    {DAMAGE_ORDER.map((k) => (
                      <Bar key={k} dataKey={k} fill={DAMAGE_META[k].barColor} radius={[3, 3, 0, 0]} name={k} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Structural class breakdown */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="font-semibold text-gray-900">Structural Class</h3>
            <p className="text-xs text-gray-400 mt-0.5 mb-5">Overall damage distribution</p>
            <div className="space-y-4">
              {loading
                ? Array(4).fill(null).map((_, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <Skeleton className="h-3 w-16" />
                      <Skeleton className="flex-1 h-2" />
                      <Skeleton className="h-3 w-8" />
                    </div>
                  ))
                : structuralBars.map((s) => (
                    <div key={s.key} className="flex items-center gap-3">
                      <span className="text-sm text-gray-600 w-20 shrink-0">{s.label}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-2">
                        <div
                          className="h-2 rounded-full transition-all duration-700"
                          style={{ width: `${s.pct}%`, background: s.color }}
                        />
                      </div>
                      <span className="text-sm font-medium text-gray-900 w-10 text-right">
                        {s.pct}%
                      </span>
                    </div>
                  ))
              }
            </div>
            {!loading && total > 0 && (
              <p className="text-xs text-gray-400 mt-5 pt-4 border-t border-gray-50">
                Based on {fmt(total)} total predictions
              </p>
            )}
          </div>
        </div>

        {/* Recent Inference Jobs */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div>
              <h3 className="font-semibold text-gray-900">Recent Inference Jobs</h3>
              <p className="text-xs text-gray-400 mt-0.5">Latest ML pipeline runs</p>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-50">
                {["JOB", "MODEL", "VERSION", "STATUS", "STARTED", "FINISHED"].map((h) => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-gray-400 tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array(4).fill(null).map((_, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      {Array(6).fill(null).map((_, j) => (
                        <td key={j} className="px-5 py-3.5">
                          <Skeleton className="h-4 w-24" />
                        </td>
                      ))}
                    </tr>
                  ))
                : jobs?.length === 0
                ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-sm text-gray-400">
                        No inference jobs found
                      </td>
                    </tr>
                  )
                : jobs?.map((job) => {
                    const s = STATUS_STYLES[job.status?.toLowerCase()] ?? STATUS_STYLES.pending;
                    return (
                      <tr key={job.id} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-4 h-4 text-gray-400">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
                              </svg>
                            </div>
                            <div>
                              <p className="font-medium text-gray-900 text-xs">{job.job_name ?? `Job #${job.id}`}</p>
                              <p className="text-xs text-gray-400">ID: {job.id}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-gray-700 text-xs">{job.model_name ?? "—"}</td>
                        <td className="px-5 py-3.5 text-gray-500 text-xs">{job.model_version ?? "—"}</td>
                        <td className="px-5 py-3.5">
                          <span className={`text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1.5 w-fit capitalize ${s.badge}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                            {job.status ?? "unknown"}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-gray-500 text-xs">{timeSince(job.started_at)}</td>
                        <td className="px-5 py-3.5 text-gray-500 text-xs">{timeSince(job.finished_at)}</td>
                      </tr>
                    );
                  })
              }
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
};

export default OverviewPage;
