import { useAppContext } from "../context/AppContext";

const LandingPage = () => {
  const { setCurrentPage } = useAppContext();

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Navbar */}
      <nav className="flex items-center justify-between px-8 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="font-bold text-gray-900 text-base">Disaster AI</span>
        </div>
        <div className="flex items-center gap-8">
          <a className="text-sm text-gray-600 hover:text-gray-900 cursor-pointer">About</a>
          <a className="text-sm text-gray-600 hover:text-gray-900 cursor-pointer">Demo</a>
        </div>
        <button
          onClick={() => setCurrentPage("overview")}
          className="flex items-center gap-1.5 bg-gray-900 hover:bg-gray-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Open Dashboard
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
      </nav>

      {/* Hero */}
      <section className="flex flex-col lg:flex-row items-center justify-between px-12 py-16 gap-12 max-w-7xl mx-auto w-full flex-1">
        <div className="max-w-lg">
          <h1 className="text-5xl font-bold text-gray-900 leading-tight mb-4">
            AI-Powered<br />
            <span className="text-blue-500">Geospatial</span><br />
            Damage<br />
            Assessment
          </h1>
          <p className="text-gray-500 text-base leading-relaxed mb-8">
            Automate satellite imagery analysis to identify structural damage, flood zones, and debris fields in real-time with 99.8% precision.
          </p>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setCurrentPage("overview")}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
            >
              Open Dashboard
            </button>
            <button className="flex items-center gap-2 text-gray-700 font-medium px-4 py-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
              <div className="w-5 h-5 rounded-full border-2 border-gray-700 flex items-center justify-center">
                <div className="w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[7px] border-l-gray-700 ml-0.5" />
              </div>
              View Demo
            </button>
          </div>
        </div>

        {/* Map preview card */}
        <div className="relative w-full max-w-xl rounded-2xl overflow-hidden shadow-2xl border border-gray-200">
          <img
            src="https://placehold.co/580x360/e8f4f8/94a3b8?text=Map+Preview"
            alt="Map preview"
            className="w-full h-72 object-cover"
          />
          {/* Overlay badge */}
          <div className="absolute bottom-4 left-4 right-4 bg-white rounded-xl p-4 shadow-lg border border-gray-100">
            <div className="flex items-center gap-2 mb-2">
              <svg viewBox="0 0 24 24" fill="#f59e0b" className="w-4 h-4"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
              <span className="font-semibold text-gray-900 text-sm">Zone B Analysis Complete</span>
              <span className="ml-auto text-xs text-gray-400">24ms</span>
            </div>
            <div className="text-xs text-gray-500 mb-1.5">Processing Layers...</div>
            <div className="w-full bg-gray-100 rounded-full h-1.5">
              <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: "85%" }} />
            </div>
            <div className="text-right text-xs text-gray-500 mt-1">85%</div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-16 px-12">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-3">Advanced Assessment Capabilities</h2>
          <p className="text-center text-gray-500 mb-12">
            Leverage state-of-the-art computer vision to analyze disaster zones rapidly with government-grade accuracy.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: "📊",
                bg: "bg-blue-50",
                title: "Satellite Comparison",
                desc: "Compare pre and post-disaster imagery with automated change detection sliders to instantly isolate affected regions.",
              },
              {
                icon: "🔶",
                bg: "bg-orange-50",
                title: "AI Damage Overlays",
                desc: "Neural networks identify structural failures, roof damage, and debris fields with high precision overlays.",
              },
              {
                icon: "📋",
                bg: "bg-purple-50",
                title: "FEMA Metrics",
                desc: "Generate automated damage reports compliant with government standards ready for export in PDF or JSON formats.",
              },
            ].map((f) => (
              <div key={f.title} className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
                <div className={`w-10 h-10 ${f.bg} rounded-lg flex items-center justify-center text-lg mb-4`}>
                  {f.icon}
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-700 py-10 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="w-6 h-6 bg-blue-500 rounded flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="white" className="w-4 h-4"><path d="M12 2L2 7l10 5 10-5-10-5z"/></svg>
          </div>
          <span className="font-bold text-white text-lg">Disaster AI</span>
        </div>
        <p className="text-slate-300 text-sm max-w-md mx-auto">
          Empowering disaster response teams with cutting-edge AI and geospatial analysis.
        </p>
        <div className="mt-4">
          <svg viewBox="0 0 24 24" fill="#94a3b8" className="w-6 h-6 mx-auto">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
          </svg>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;