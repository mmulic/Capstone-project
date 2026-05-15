import { useAppContext } from "../context/AppContext";
import { MapContainer, TileLayer } from "react-leaflet";

const FEATURES = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-blue-600">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
    bg: "bg-blue-50",
    title: "Satellite Comparison",
    desc: "Layer pre- and post-disaster imagery directly on the map to instantly isolate affected regions at the building level.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-orange-500">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
      </svg>
    ),
    bg: "bg-orange-50",
    title: "AI Damage Overlays",
    desc: "Vision-language models classify structural damage per building — no damage, minor, major, or destroyed — with confidence scores.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-violet-500">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    bg: "bg-violet-50",
    title: "Evaluation Metrics",
    desc: "Track model accuracy, precision, recall, and F1 score against ground-truth labels with a full confusion matrix breakdown.",
  },
];



const LandingPage = () => {
  const { setCurrentPage } = useAppContext();

  return (
    <div className="min-h-screen bg-white flex flex-col">

      {/* Navbar */}
      <nav className="flex items-center justify-between px-8 py-4 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="font-bold text-gray-900 text-base">Disaster AI</span>
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
      <section className="flex-1 flex flex-col lg:flex-row items-center justify-between px-12 py-16 gap-12 max-w-7xl mx-auto w-full">

        {/* Left — text */}
        <div className="max-w-lg shrink-0">
          <div className="inline-flex items-center gap-2 bg-blue-50 border border-blue-100 text-blue-600 text-xs font-semibold px-3 py-1.5 rounded-full mb-6 uppercase tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            Hurricane Harvey · 2017
          </div>
          <h1 className="text-5xl font-bold text-gray-900 leading-tight mb-5">
            AI-Powered{" "}
            <span className="text-blue-600">Disaster Damage</span>{" "}
            Assessment
          </h1>
          <p className="text-gray-500 text-base leading-relaxed mb-8">
            Automatically classify building-level structural damage from satellite imagery using vision-language models — helping response teams prioritize faster.
          </p>
          <button
            onClick={() => setCurrentPage("overview")}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-8 py-3.5 rounded-xl transition-colors shadow-sm text-base"
          >
            Open Dashboard
          </button>

        </div>

        {/* Right — live map preview */}
        <div className="w-full max-w-xl rounded-2xl overflow-hidden shadow-2xl border border-gray-200 shrink-0">
          {/* Map label bar */}
          <div className="bg-white border-b border-gray-100 px-4 py-2.5">
            <span className="text-xs font-medium text-gray-600">Houston, TX</span>
          </div>
          <MapContainer
            center={[29.774, -95.369]}
            zoom={13}
            style={{ height: 340, width: "100%" }}
            zoomControl={false}
            dragging={false}
            scrollWheelZoom={false}
            doubleClickZoom={false}
            attributionControl={false}
          >
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          </MapContainer>
        </div>

      </section>

      {/* Features */}
      <section className="border-t border-gray-100 py-16 px-8">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-3">
            Assessment Capabilities
          </h2>
          <p className="text-center text-gray-400 mb-12 max-w-xl mx-auto text-sm">
            From raw satellite imagery to building-level damage classifications — all in one platform.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl p-6 border border-gray-100 hover:border-gray-200 transition-colors">
                <div className={`w-10 h-10 ${f.bg} rounded-lg flex items-center justify-center mb-4`}>
                  {f.icon}
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-50 border-t border-gray-200 py-6 text-center">
        <div className="flex items-center justify-center gap-2 mb-1">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="font-bold text-gray-900 text-base">Disaster AI</span>
        </div>
        <p className="text-gray-400 text-xs">
          Empowering disaster response teams with AI and geospatial analysis.
        </p>
      </footer>

    </div>
  );
};

export default LandingPage;
