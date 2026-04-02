import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

const METRICS = [
  { label: "Model Accuracy", value: "94.2%", delta: "+2.1%", sub: "vs 92.1% baseline",        up: true  },
  { label: "Precision",      value: "91.5%", delta: "+1.5%", sub: "High confidence matches",   up: true  },
  { label: "Recall",         value: "89.0%", delta: "−0.4%", sub: "Sensitivity metric",        up: false },
  { label: "F1 Score",       value: "0.90",  delta: "+0.8%", sub: "Harmonic mean",             up: true  },
];

const MATRIX = [
  { true: "None",      pred: [452, 32, 4, 0]   },
  { true: "Minor",     pred: [28,  310, 41, 2]  },
  { true: "Major",     pred: [5,   38, 289, 45] },
  { true: "Destroyed", pred: [0,   3,  21, 156] },
];
const LABELS = ["None", "Minor", "Major", "Destroyed"];
const DIAG = [452, 310, 289, 156];

const DIST_DATA = [
  { category: "NONE",      ai: 420, fema: 430 },
  { category: "MINOR",     ai: 310, fema: 380 },
  { category: "MAJOR",     ai: 290, fema: 260 },
  { category: "DESTROYED", ai: 170, fema: 180 },
];

const cellColor = (val, isDiag) => {
  if (isDiag) {
    if (val > 300) return "bg-blue-600 text-white";
    if (val > 100) return "bg-blue-400 text-white";
    return "bg-blue-300 text-white";
  }
  if (val === 0) return "bg-gray-50 text-gray-300";
  return "bg-blue-100 text-blue-800";
};

const REGIONS = ["Hurricane Ian - Zone A (North)", "Hurricane Ian - Zone B", "Hurricane Idalia - Zone A", "All Zones"];

const MetricsPage = () => {
  const [region, setRegion] = useState(REGIONS[0]);
  const [mismatchOnly, setMismatchOnly] = useState(false);

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
              <span className="text-gray-700">Evaluation & Metrics</span>
            </nav>
            <h1 className="text-2xl font-bold text-gray-900">Evaluation & Metrics</h1>
            <p className="text-sm text-gray-500 mt-1 max-w-xl">
              Comparing AI damage predictions against FEMA ground truth data across Hurricane Ian zones.
            </p>
          </div>
          <button className="flex items-center gap-2 border border-gray-200 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-50 shadow-sm">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
            Export Report
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4 flex flex-wrap items-center gap-6">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Region</p>
            <div className="relative">
              <select
                value={region}
                onChange={e => setRegion(e.target.value)}
                className="appearance-none border border-gray-200 rounded-lg px-3 py-2 pr-8 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {REGIONS.map(r => <option key={r}>{r}</option>)}
              </select>
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"><path d="M7 10l5 5 5-5z"/></svg>
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Filter Data</p>
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                onClick={() => setMismatchOnly(v => !v)}
                className={`w-10 h-5 rounded-full relative transition-colors ${mismatchOnly ? "bg-blue-600" : "bg-gray-200"}`}
              >
                <div className={`w-4 h-4 bg-white rounded-full absolute top-0.5 transition-all ${mismatchOnly ? "left-5" : "left-0.5"}`}/>
              </div>
              <span className="text-sm text-gray-700">View Mismatches Only</span>
            </label>
          </div>
          <div className="ml-auto flex items-center gap-2 text-sm text-gray-400">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
            Last updated: 2 hours ago
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {METRICS.map((m) => (
            <div key={m.label} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-start justify-between mb-3">
                <p className="text-sm text-gray-600">{m.label}</p>
                <span className={`text-xs font-semibold flex items-center gap-0.5 ${m.up ? "text-green-500" : "text-red-500"}`}>
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">{m.up ? <path d="M7 14l5-5 5 5z"/> : <path d="M7 10l5 5 5-5z"/>}</svg>
                  {m.delta}
                </span>
              </div>
              <p className="text-3xl font-bold text-gray-900 mb-1">{m.value}</p>
              <p className="text-xs text-gray-400">{m.sub}</p>
              <div className="mt-3 h-1 bg-blue-500 rounded-full w-2/3" />
            </div>
          ))}
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
          {/* Confusion Matrix */}
          <div className="xl:col-span-3 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Confusion Matrix</h3>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-100 rounded-sm inline-block border border-gray-200"/>Low</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-600 rounded-sm inline-block"/>High</span>
              </div>
            </div>
            <div className="flex">
              {/* Y-axis label */}
              <div className="flex items-center mr-2">
                <p className="text-xs text-gray-400 -rotate-90 whitespace-nowrap" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
                  TRUE LABEL (FEMA)
                </p>
              </div>
              <div className="flex-1">
                {/* Column headers */}
                <div className="flex mb-1 ml-16">
                  {LABELS.map(l => (
                    <div key={l} className="flex-1 text-center text-xs text-gray-400 font-medium">{l}</div>
                  ))}
                </div>
                {/* Rows */}
                {MATRIX.map((row, ri) => (
                  <div key={ri} className="flex items-center mb-1">
                    <div className="w-16 text-xs text-gray-400 font-medium text-right pr-2">{row.true}</div>
                    {row.pred.map((val, ci) => {
                      const isDiag = ri === ci;
                      return (
                        <div
                          key={ci}
                          className={`flex-1 aspect-square flex items-center justify-center text-sm font-bold rounded mx-0.5 ${cellColor(val, isDiag)}`}
                          style={{ minHeight: 56 }}
                        >
                          {val}
                        </div>
                      );
                    })}
                  </div>
                ))}
                <p className="text-center text-xs text-gray-400 font-semibold mt-2 tracking-widest uppercase">Predicted Label (AI)</p>
              </div>
            </div>
          </div>

          {/* Distribution chart */}
          <div className="xl:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-start justify-between mb-4">
              <h3 className="font-semibold text-gray-900 leading-tight">Distribution by<br/>Severity</h3>
              <div className="flex flex-col gap-1 text-xs text-gray-500">
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-blue-600 rounded-sm inline-block"/>AI Predicted</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-orange-500 rounded-sm inline-block"/>FEMA Ground Truth</span>
              </div>
            </div>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={DIST_DATA} barCategoryGap="25%" barGap={2} margin={{ top: 0, right: 0, bottom: 0, left: -25 }}>
                  <XAxis dataKey="category" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
                  <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}/>
                  <Bar dataKey="ai"   fill="#3b82f6" radius={[3,3,0,0]} name="AI Predicted"/>
                  <Bar dataKey="fema" fill="#f97316" radius={[3,3,0,0]} name="FEMA Ground Truth"/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricsPage;