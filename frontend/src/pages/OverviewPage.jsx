import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart, CartesianGrid
} from "recharts";

const TREND_DATA = [
  { day: "MON", detected: 340, baseline: 300 },
  { day: "TUE", detected: 280, baseline: 310 },
  { day: "WED", detected: 350, baseline: 320 },
  { day: "THU", detected: 300, baseline: 315 },
  { day: "FRI", detected: 420, baseline: 325 },
  { day: "SAT", detected: 510, baseline: 330 },
  { day: "SUN", detected: 620, baseline: 340 },
];

const RUNS = [
  { id: "#RUN-8832", sector: "Sector 4B - Residential", sub: "Keaton Beach Area",    status: "Completed",  pct: 100, color: "bg-green-500",  date: "Oct 24, 2023" },
  { id: "#RUN-8833", sector: "Sector 1A - Industrial",  sub: "Perry Manufacturing",  status: "Processing", pct: 45,  color: "bg-blue-500",   date: "Oct 24, 2023" },
  { id: "#RUN-8830", sector: "Sector 2C - Mixed Use",   sub: "Downtown Core",        status: "Failed",     pct: 12,  color: "bg-red-500",    date: "Oct 23, 2023" },
];

const STATUS_STYLES = {
  Completed:  "bg-green-50 text-green-700",
  Processing: "bg-blue-50 text-blue-700",
  Failed:     "bg-red-50 text-red-600",
};

const STRUCTURAL = [
  { label: "No Damage", pct: 25, color: "bg-green-500" },
  { label: "Minor",     pct: 35, color: "bg-blue-400"  },
  { label: "Major",     pct: 30, color: "bg-orange-400" },
  { label: "Destroyed", pct: 10, color: "bg-red-500"   },
];

const KPI_CARDS = [
  { label: "Total Regions Scanned",  value: "12,450", delta: "+12%", color: "text-green-500", icon: "🔵" },
  { label: "Destroyed Structures",   value: "4,302",  delta: "+8.5%", color: "text-green-500", icon: "🏚️" },
  { label: "Model Confidence",       value: "94.8%",  delta: "+1.2%", color: "text-green-500", icon: "🎯" },
  { label: "FEMA Agreement",         value: "89%",    delta: "+2.4%", color: "text-green-500", icon: "🛡️" },
];

const OverviewPage = () => {
  const [filterOpen, setFilterOpen] = useState(false);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
      {/* Top bar */}
      <header className="flex items-center gap-4 px-6 py-3.5 bg-white border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900">Hurricane Idalia - 2023</span>
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-gray-400"><path d="M7 10l5 5 5-5z"/></svg>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse inline-block"/>
          <span className="text-green-600 font-medium">Live</span>
          <span className="text-gray-400 ml-1">Last updated: 12 min ago</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 w-56">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-gray-400"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
            <span className="text-sm text-gray-400">Search locations, reports...</span>
          </div>
          <button className="relative p-2 hover:bg-gray-50 rounded-lg">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-gray-500"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full"/>
          </button>
          <button className="p-2 hover:bg-gray-50 rounded-lg">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-gray-500"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/></svg>
          </button>
        </div>
      </header>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {KPI_CARDS.map((k) => (
            <div key={k.label} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-xl">{k.icon}</div>
                <span className={`text-xs font-semibold ${k.color} flex items-center gap-0.5`}>
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path d="M7 14l5-5 5 5z"/></svg>
                  {k.delta}
                </span>
              </div>
              <p className="text-gray-500 text-xs mb-1">{k.label}</p>
              <p className="text-2xl font-bold text-gray-900">{k.value}</p>
            </div>
          ))}
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          {/* Trend line chart */}
          <div className="xl:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-start justify-between mb-1">
              <div>
                <h3 className="font-semibold text-gray-900">Damage Severity Trends</h3>
                <p className="text-xs text-gray-400 mt-0.5">Detection rate over last 7 days</p>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block"/>Detected</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-gray-300 inline-block"/>Baseline</span>
              </div>
            </div>
            <div className="h-52 mt-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={TREND_DATA} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#f1f5f9" strokeDasharray="0"/>
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
                  <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}/>
                  <Area type="monotone" dataKey="baseline" stroke="#d1d5db" strokeWidth={1.5} fill="none" dot={false}/>
                  <Area type="monotone" dataKey="detected" stroke="#3b82f6" strokeWidth={2} fill="url(#grad)" dot={{ r: 4, fill: "#3b82f6", strokeWidth: 0 }} activeDot={{ r: 6 }}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Structural Class */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="font-semibold text-gray-900">Structural Class</h3>
            <p className="text-xs text-gray-400 mt-0.5 mb-6">Damage distribution analysis</p>
            <div className="space-y-4">
              {STRUCTURAL.map((s) => (
                <div key={s.label} className="flex items-center gap-3">
                  <span className="text-sm text-gray-600 w-20">{s.label}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div className={`${s.color} h-2 rounded-full`} style={{ width: `${s.pct * 3}px`, maxWidth: "100%" }}/>
                  </div>
                  <span className="text-sm font-medium text-gray-900 w-8 text-right">{s.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Runs Table */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div>
              <h3 className="font-semibold text-gray-900">Recent AI Assessment Runs</h3>
              <p className="text-xs text-gray-400 mt-0.5">Latest automated structural analysis jobs</p>
            </div>
            <button
              onClick={() => setFilterOpen(v => !v)}
              className="flex items-center gap-2 text-sm text-gray-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M4.25 5.61C6.27 8.2 10 13 10 13v6c0 .55.45 1 1 1h2c.55 0 1-.45 1-1v-6s3.72-4.8 5.74-7.39A.998.998 0 0019 4H5c-.72 0-1.16.81-.75 1.61z"/></svg>
              Filter
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-50">
                {["RUN ID", "SECTOR / LOCATION", "STATUS", "COMPLETION", "DATE", "ACTIONS"].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-gray-400 tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {RUNS.map((r) => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                  <td className="px-5 py-3.5 text-blue-600 font-medium">{r.id}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-teal-100 flex items-center justify-center text-xs">🗺</div>
                      <div>
                        <p className="font-medium text-gray-900">{r.sector}</p>
                        <p className="text-xs text-gray-400">{r.sub}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1.5 w-fit ${STATUS_STYLES[r.status]}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${r.color}`}/>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5 w-24">
                        <div className={`${r.color} h-1.5 rounded-full`} style={{ width: `${r.pct}%` }}/>
                      </div>
                      <span className="text-xs text-gray-500">{r.pct}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-gray-500">{r.date}</td>
                  <td className="px-5 py-3.5">
                    <button className="text-gray-400 hover:text-gray-600 p-1">
                      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default OverviewPage;