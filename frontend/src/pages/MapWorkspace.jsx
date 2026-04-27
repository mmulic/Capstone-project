import { useState, useEffect, useRef, useMemo } from "react";
import { MapContainer, TileLayer, ImageOverlay, CircleMarker, Polygon, Tooltip, useMap } from "react-leaflet";
import { useAppContext } from "../context/AppContext.jsx";
import { postQuery, getDamageData } from "../services/api.js";
import {
  loadHarveyData,
  getSceneOptions,
  getScenePreview,
  getSceneBounds,
  getSceneCentroids,
  getSceneBuildingUids,
  loadScenePolygons,
  DAMAGE_COLOR,
  DAMAGE_LABEL,
} from "../data/harveyAdapter.js";

const MAP_CENTER = [29.758, -95.367];
const MAP_ZOOM = 11;

const TILE_LAYERS = {
  streets: {
    layers: [
      {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      },
    ],
  },
  hybrid: {
    layers: [
      {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attribution: '&copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics',
      },
      {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attribution: "",
      },
    ],
  },
};

// ─── Shared utilities ────────────────────────────────────────────────────────

function LoadingOverlay({ message }) {
  return (
    <div className="absolute inset-0 z-[2000] flex items-center justify-center bg-white/80">
      <div className="text-center space-y-2">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-gray-500">{message}</p>
      </div>
    </div>
  );
}

// Flies the map to the given bounds whenever bounds changes.
function FlyToBounds({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { animate: true, padding: [20, 20] });
  }, [bounds, map]);
  return null;
}

// ─── Left Panel ──────────────────────────────────────────────────────────────

function ModeToggle() {
  const { imageryLayer, setImageryLayer } = useAppContext();
  return (
    <div>
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">View Mode</p>
      <div className="flex rounded-lg border border-gray-200 overflow-hidden">
        {["pre", "post", "overlay"].map((mode) => (
          <button key={mode} onClick={() => setImageryLayer(mode)}
            className={`flex-1 py-1.5 text-xs font-medium capitalize transition-colors ${imageryLayer === mode ? "bg-blue-600 text-white" : "text-gray-500 hover:bg-gray-50"}`}>
            {mode}
          </button>
        ))}
      </div>
    </div>
  );
}

function HarveySceneSelector({ sceneOptions }) {
  const { selectedSceneId, setSelectedSceneId } = useAppContext();
  const [search, setSearch] = useState("");
  const listRef = useRef(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return sceneOptions;
    return sceneOptions.filter(
      (s) => s.label.toLowerCase().includes(q) ||
             (s.preDate && s.preDate.toLowerCase().includes(q)) ||
             (s.postDate && s.postDate.toLowerCase().includes(q))
    );
  }, [sceneOptions, search]);

  useEffect(() => {
    if (!listRef.current || !selectedSceneId) return;
    const el = listRef.current.querySelector(`[data-scene="${selectedSceneId}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedSceneId]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Scene Selection</p>
      <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 mb-2">
        <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5 text-gray-400 shrink-0">
          <path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter scenes…"
          className="bg-transparent text-xs text-gray-600 placeholder-gray-400 outline-none w-full"
        />
        {search && (
          <button onClick={() => setSearch("")} className="text-gray-300 hover:text-gray-500 transition-colors">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        )}
      </div>
      <p className="text-[10px] text-gray-400 mb-1.5">{filtered.length} of {sceneOptions.length} scenes</p>
      <div ref={listRef} className="flex-1 overflow-y-auto space-y-0.5 min-h-0">
        {filtered.map((s) => {
          const isSelected = s.sceneId === selectedSceneId;
          return (
            <button
              key={s.sceneId}
              data-scene={s.sceneId}
              onClick={() => setSelectedSceneId(s.sceneId)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${isSelected ? "bg-blue-600 text-white" : "hover:bg-gray-50 text-gray-700"}`}>
              <p className={`text-xs font-semibold leading-tight ${isSelected ? "text-white" : "text-gray-800"}`}>{s.label}</p>
              <p className={`text-[10px] mt-0.5 ${isSelected ? "text-blue-100" : "text-gray-400"}`}>
                {s.preDate ?? "—"} → {s.postDate ?? "—"}
              </p>
            </button>
          );
        })}
        {filtered.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">No scenes match</p>
        )}
      </div>
    </div>
  );
}

function BasemapToggle({ basemap, setBasemap }) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Base Map</p>
      <div className="flex rounded-lg border border-gray-200 overflow-hidden">
        {[
          { id: "streets", label: "Streets" },
          { id: "hybrid",  label: "Hybrid"  },
        ].map(({ id, label }) => (
          <button key={id} onClick={() => setBasemap(id)}
            className={`flex-1 py-1.5 text-xs font-medium transition-colors ${basemap === id ? "bg-blue-600 text-white" : "text-gray-500 hover:bg-gray-50"}`}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function LeftPanel({ sceneOptions, basemap, setBasemap }) {
  const { imageryLayer } = useAppContext();
  return (
    <div className="w-64 shrink-0 bg-white border-r border-gray-100 flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 shrink-0">
        <h2 className="font-semibold text-gray-900 text-sm">Layer Control</h2>
      </div>
      <div className="flex flex-col px-4 py-4 space-y-5 text-sm flex-1 min-h-0 overflow-hidden">
        <ModeToggle />
        <BasemapToggle basemap={basemap} setBasemap={setBasemap} />
        <HarveySceneSelector sceneOptions={sceneOptions} />
      </div>
    </div>
  );
}

// ─── Geo Map Workspace (all three modes) ─────────────────────────────────────

function GeoMapWorkspace({ sceneOptions, basemap }) {
  const { imageryLayer, setImageryLayer, harveyData, selectedSceneId, setSelectedSceneId } = useAppContext();

  const preview = useMemo(
    () => (harveyData && selectedSceneId ? getScenePreview(harveyData, selectedSceneId) : null),
    [harveyData, selectedSceneId]
  );

  const bounds = useMemo(
    () => (harveyData && selectedSceneId ? getSceneBounds(harveyData, selectedSceneId) : null),
    [harveyData, selectedSceneId]
  );

  const sceneCentroids = useMemo(
    () => (harveyData ? getSceneCentroids(harveyData) : []),
    [harveyData]
  );

  // All Harvey predictions — fetched once when overlay mode is first entered
  const allPredictionsRef = useRef(null);
  const [predictionsReady, setPredictionsReady] = useState(false);

  useEffect(() => {
    if (imageryLayer !== "overlay") return;
    if (allPredictionsRef.current !== null) return; // already fetched
    allPredictionsRef.current = []; // mark as in-flight
    getDamageData({ disaster: "hurricane-harvey" })
      .then((geojson) => {
        allPredictionsRef.current = geojson?.features ?? [];
        setPredictionsReady(true);
      })
      .catch(() => {
        allPredictionsRef.current = [];
        setPredictionsReady(true);
      });
  }, [imageryLayer]);

  // Per-scene damage state: { predictions: Feature[], polygons: { uid: [[lat,lng],...] } }
  const [damageFeatures, setDamageFeatures] = useState({ predictions: [], polygons: {} });
  const [damageLoading, setDamageLoading] = useState(false);

  useEffect(() => {
    if (imageryLayer !== "overlay" || !selectedSceneId || !harveyData) {
      setDamageFeatures({ predictions: [], polygons: {} });
      return;
    }
    // Wait for the global predictions fetch to complete
    if (!predictionsReady && allPredictionsRef.current === null) return;

    let cancelled = false;
    setDamageLoading(true);

    const sceneUids = getSceneBuildingUids(harveyData, selectedSceneId);
    const scenePredictions = (allPredictionsRef.current ?? []).filter(
      (f) => sceneUids.has(f.properties.external_id)
    );

    loadScenePolygons(selectedSceneId).then((polygons) => {
      if (!cancelled) {
        setDamageFeatures({ predictions: scenePredictions, polygons });
        setDamageLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, [imageryLayer, selectedSceneId, harveyData, predictionsReady]);

  // Overlay mode shows post imagery; pre/post modes show their respective image
  const imgSrc = imageryLayer === "pre" ? preview?.preImagePath : preview?.postImagePath;
  const imgDate = imageryLayer === "pre" ? preview?.preDate : preview?.postDate;

  const currentIdx = sceneOptions.findIndex((s) => s.sceneId === selectedSceneId);
  const prevScene = currentIdx > 0 ? sceneOptions[currentIdx - 1] : null;
  const nextScene = currentIdx < sceneOptions.length - 1 ? sceneOptions[currentIdx + 1] : null;

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "ArrowLeft" && prevScene) setSelectedSceneId(prevScene.sceneId);
      if (e.key === "ArrowRight" && nextScene) setSelectedSceneId(nextScene.sceneId);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [prevScene, nextScene, setSelectedSceneId]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative">
      {/* Top bar */}
      <div className="shrink-0 flex items-center justify-between px-5 py-2.5 bg-white border-b border-gray-100">
        <div className="flex items-center gap-3">
          {preview && (
            <>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                imageryLayer === "pre"
                  ? "bg-blue-500/20 text-blue-700 border border-blue-500/30"
                  : imageryLayer === "post"
                  ? "bg-orange-500/20 text-orange-700 border border-orange-500/30"
                  : "bg-purple-500/20 text-purple-700 border border-purple-500/30"
              }`}>
                {imageryLayer === "overlay" ? "overlay" : `${imageryLayer}-disaster`}
              </span>
              <span className="text-sm font-semibold text-gray-800">Scene #{preview.shortId}</span>
              {imgDate && <span className="text-xs text-gray-400">{imgDate}</span>}
            </>
          )}
          {!preview && (
            <span className="text-sm text-gray-400">Select a scene to view imagery</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {preview && (
            <span className="text-xs text-gray-400">
              {currentIdx + 1} / {sceneOptions.length}
            </span>
          )}
          {/* Pre / Post quick-toggle in the bar */}
          {preview && imageryLayer !== "overlay" && (
            <div className="flex rounded border border-gray-200 overflow-hidden">
              {["pre", "post"].map((p) => (
                <button key={p} onClick={() => setImageryLayer(p)}
                  className={`text-[10px] font-bold px-2.5 py-1 uppercase tracking-wider transition-colors ${imageryLayer === p ? "bg-blue-600 text-white" : "text-gray-500 hover:text-gray-700"}`}>
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} className="w-full h-full" zoomControl>
          {TILE_LAYERS[basemap].layers.map((layer, i) => (
            <TileLayer key={`${basemap}-${i}`} url={layer.url} attribution={layer.attribution} />
          ))}

          {/* Geo-referenced scene imagery */}
          {bounds && imgSrc && (
            <ImageOverlay
              key={`${selectedSceneId}-${imageryLayer}`}
              url={imgSrc}
              bounds={bounds}
              opacity={1}
            />
          )}

          {/* Scene location markers — visible at all zoom levels */}
          {sceneCentroids.map((sc) => {
            const isSelected = sc.sceneId === selectedSceneId;
            return (
              <CircleMarker
                key={sc.sceneId}
                center={[sc.lat, sc.lng]}
                radius={isSelected ? 10 : 6}
                pathOptions={{
                  fillColor: isSelected ? "#2563eb" : "#93c5fd",
                  color: isSelected ? "#1d4ed8" : "#3b82f6",
                  weight: isSelected ? 2.5 : 1.5,
                  fillOpacity: isSelected ? 0.95 : 0.6,
                }}
                eventHandlers={{ click: () => setSelectedSceneId(sc.sceneId) }}>
                <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
                  <span className="text-xs font-semibold">Scene #{sc.shortId}</span>
                </Tooltip>
              </CircleMarker>
            );
          })}

          {/* Fly to scene bounds when selection changes */}
          {bounds && <FlyToBounds bounds={bounds} />}

          {/* VLM damage polygons — overlay mode only */}
          {imageryLayer === "overlay" && damageFeatures.predictions.map((f, i) => {
            const { damage_class, confidence, color, rationale } = f.properties;
            const uid = f.properties.external_id;
            const label = damage_class?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
            const fill = color ?? "#94a3b8";
            const tooltip = (
              <Tooltip sticky opacity={0.97}>
                <div className="text-xs space-y-0.5">
                  <p className="font-semibold">{label}</p>
                  {confidence != null && (
                    <p className="text-gray-500">Confidence: {Math.round(confidence * 100)}%</p>
                  )}
                  {rationale && (
                    <p className="text-gray-400 max-w-[180px] leading-snug">{rationale}</p>
                  )}
                </div>
              </Tooltip>
            );

            const positions = damageFeatures.polygons[uid];
            if (positions?.length >= 3) {
              return (
                <Polygon
                  key={uid ?? i}
                  positions={positions}
                  pathOptions={{ fillColor: fill, color: "#fff", weight: 1.5, fillOpacity: 0.4 }}>
                  {tooltip}
                </Polygon>
              );
            }
            // Fallback: if polygon not available, render a point
            const [lng, lat] = f.geometry.coordinates;
            return (
              <CircleMarker
                key={uid ?? i}
                center={[lat, lng]}
                radius={6}
                pathOptions={{ fillColor: fill, color: "#fff", weight: 1.5, fillOpacity: 0.9 }}>
                {tooltip}
              </CircleMarker>
            );
          })}
        </MapContainer>

        {/* Damage data loading indicator */}
        {damageLoading && (
          <div className="absolute top-3 right-3 z-[1000] bg-white rounded-lg shadow border border-gray-100 px-3 py-2 flex items-center gap-2 text-xs text-gray-500">
            <div className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Loading damage data…
          </div>
        )}

        {/* Damage polygon count badge */}
        {imageryLayer === "overlay" && !damageLoading && damageFeatures.predictions.length > 0 && (
          <div className="absolute top-3 right-3 z-[1000] bg-white rounded-lg shadow border border-gray-100 px-3 py-2 text-xs text-gray-600">
            <span className="font-semibold text-gray-800">{damageFeatures.predictions.length}</span> assessed properties
          </div>
        )}

        {/* No-bounds notice for the 9 unannotated scenes */}
        {selectedSceneId && !bounds && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] bg-white rounded-lg shadow border border-amber-200 px-3 py-2 text-xs text-amber-700">
            No geographic bounds available for this scene — imagery cannot be placed on map.
          </div>
        )}

      </div>

      {/* Bottom navigation bar */}
      {preview && (
        <div className="shrink-0 flex items-center justify-between px-5 py-3 bg-white border-t border-gray-100">
          <button onClick={() => prevScene && setSelectedSceneId(prevScene.sceneId)} disabled={!prevScene}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-800 disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z"/></svg>
            {prevScene ? `Scene #${prevScene.shortId}` : "Previous"}
          </button>
          <span className="text-[10px] text-gray-400 font-mono">
            {bounds
              ? `${bounds[0][0].toFixed(4)}, ${bounds[0][1].toFixed(4)} → ${bounds[1][0].toFixed(4)}, ${bounds[1][1].toFixed(4)}`
              : "No bounds"}
          </span>
          <button onClick={() => nextScene && setSelectedSceneId(nextScene.sceneId)} disabled={!nextScene}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-800 disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
            {nextScene ? `Scene #${nextScene.shortId}` : "Next"}
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Right Panel ─────────────────────────────────────────────────────────────

function SceneMetadataPanel() {
  const { harveyData, selectedSceneId, imageryLayer } = useAppContext();

  const preview = useMemo(
    () => (harveyData && selectedSceneId ? getScenePreview(harveyData, selectedSceneId) : null),
    [harveyData, selectedSceneId]
  );

  const bounds = useMemo(
    () => (harveyData && selectedSceneId ? getSceneBounds(harveyData, selectedSceneId) : null),
    [harveyData, selectedSceneId]
  );

  if (!preview) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400 p-4 text-center">
        {harveyData ? "Select a scene to view details" : "Loading…"}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
      <div>
        <p className="text-xs text-gray-400">Selected Scene</p>
        <p className="font-bold text-gray-900 text-base">Scene #{preview.shortId}</p>
      </div>

      <div className="text-xs text-gray-500 space-y-1">
        <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Disaster</span><span className="text-gray-700 capitalize">{preview.disaster?.replace(/-/g, " ")}</span></div>
        <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Type</span><span className="text-gray-700 capitalize">{preview.disasterType}</span></div>
        <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Pre date</span><span className="text-gray-700">{preview.preDate}</span></div>
        <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Post date</span><span className="text-gray-700">{preview.postDate}</span></div>
        <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Buildings</span><span className="text-gray-700">{preview.buildingCount?.post ?? preview.buildingCount?.pre ?? "—"} annotated</span></div>
        {preview.centroid && (
          <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Center</span><span className="text-gray-700 font-mono text-[10px]">{preview.centroid.lat.toFixed(4)}, {preview.centroid.lng.toFixed(4)}</span></div>
        )}
        {bounds && (
          <div className="flex gap-2 items-start"><span className="w-20 shrink-0 text-gray-400">Bounds</span>
            <span className="text-gray-700 font-mono text-[10px] leading-relaxed">
              SW {bounds[0][0].toFixed(4)}, {bounds[0][1].toFixed(4)}<br />
              NE {bounds[1][0].toFixed(4)}, {bounds[1][1].toFixed(4)}
            </span>
          </div>
        )}
      </div>

      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Scene Imagery</p>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <p className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">Pre</p>
            <div className={`rounded-lg overflow-hidden bg-gray-100 aspect-square ring-2 transition-all ${imageryLayer === "pre" ? "ring-blue-500" : "ring-transparent"}`}>
              {preview.preImagePath
                ? <img src={preview.preImagePath} alt="Pre" className="w-full h-full object-cover" />
                : <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-400">—</div>
              }
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">Post</p>
            <div className={`rounded-lg overflow-hidden bg-gray-100 aspect-square ring-2 transition-all ${imageryLayer === "post" || imageryLayer === "overlay" ? "ring-orange-500" : "ring-transparent"}`}>
              {preview.postImagePath
                ? <img src={preview.postImagePath} alt="Post" className="w-full h-full object-cover" />
                : <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-400">—</div>
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AIAssistantTab() {
  const { chatHistory, setChatHistory, selectedSceneId } = useAppContext();
  const [inputVal, setInputVal] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const send = async () => {
    const text = inputVal.trim();
    if (!text || sending) return;
    setInputVal("");
    setSending(true);
    setChatHistory((h) => [...h, { role: "user", text, id: Date.now() }]);
    try {
      const res = await postQuery(text, selectedSceneId ? { sceneId: selectedSceneId } : {});
      setChatHistory((h) => [...h, { role: "assistant", text: res.answer || res.message || "No response.", id: Date.now() + 1 }]);
    } catch {
      setChatHistory((h) => [...h, { role: "assistant", text: "Backend not connected. Set VITE_API_BASE_URL in .env to enable AI responses.", id: Date.now() + 1 }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {chatHistory.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center mx-auto mb-3">
              <svg viewBox="0 0 24 24" fill="#3b82f6" className="w-5 h-5"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>
            </div>
            <p className="text-sm font-medium text-gray-700">AI Assistant</p>
            <p className="text-xs text-gray-400 mt-1">Ask about this scene or Harvey dataset</p>
          </div>
        ) : (
          chatHistory.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${msg.role === "user" ? "bg-blue-600 text-white rounded-tr-sm" : "bg-gray-100 text-gray-800 rounded-tl-sm"}`}>
                {msg.text}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
      <div className="p-3 border-t border-gray-100">
        <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 focus-within:border-blue-400 transition-colors">
          <input
            type="text" value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about this scene…"
            className="flex-1 bg-transparent text-sm text-gray-700 placeholder-gray-400 outline-none"
          />
          <button onClick={send} disabled={sending || !inputVal.trim()}
            className="w-7 h-7 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 flex items-center justify-center shrink-0 transition-colors">
            <svg viewBox="0 0 24 24" fill="white" className="w-3.5 h-3.5"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function RightPanel() {
  const { rightTab, setRightTab } = useAppContext();
  return (
    <div className="w-72 shrink-0 bg-white border-l border-gray-100 flex flex-col">
      <div className="flex border-b border-gray-100 shrink-0">
        {[{ id: "details", label: "Scene Details" }, { id: "assistant", label: "AI Assistant" }].map((tab) => (
          <button key={tab.id} onClick={() => setRightTab(tab.id)}
            className={`flex-1 py-3 text-xs font-semibold transition-colors ${rightTab === tab.id ? "text-blue-600 border-b-2 border-blue-600" : "text-gray-400 hover:text-gray-600"}`}>
            {tab.label}
          </button>
        ))}
      </div>
      {rightTab === "details"   && <SceneMetadataPanel />}
      {rightTab === "assistant" && <AIAssistantTab />}
    </div>
  );
}

// ─── Root workspace ──────────────────────────────────────────────────────────

export default function MapWorkspace() {
  const { imageryLayer, setCurrentPage, harveyData, setHarveyData, selectedSceneId, setSelectedSceneId } = useAppContext();
  const [loadError, setLoadError] = useState(null);
  const [basemap, setBasemap] = useState("streets"); // "streets" | "satellite"

  useEffect(() => {
    if (harveyData) return;
    loadHarveyData()
      .then((data) => {
        setHarveyData(data);
        if (data.scenes.length > 0) setSelectedSceneId(data.scenes[0].sceneId);
      })
      .catch((e) => setLoadError(e.message));
  }, [harveyData, setHarveyData, setSelectedSceneId]);

  const sceneOptions = useMemo(
    () => (harveyData ? getSceneOptions(harveyData) : []),
    [harveyData]
  );

  const breadcrumbSuffix = imageryLayer === "pre"
    ? "Pre-Disaster Imagery"
    : imageryLayer === "post"
    ? "Post-Disaster Imagery"
    : "Overlay Map";

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-2.5 bg-white border-b border-gray-100 shrink-0">
        <nav className="flex items-center gap-1.5 text-sm text-gray-400">
          <button onClick={() => setCurrentPage("overview")} className="hover:text-blue-600 transition-colors">Projects</button>
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          <span className="text-gray-500">Hurricane Harvey</span>
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          <span className="text-gray-900 font-medium">{breadcrumbSuffix}</span>
        </nav>
        <div className="flex items-center gap-2">
          <button className="text-xs font-medium px-3 py-1.5 rounded-lg bg-blue-600 text-white">
            Map View
          </button>
          <button className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors">
            Export Report
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden relative">
        {!harveyData && !loadError && <LoadingOverlay message="Loading Harvey dataset…" />}
        {loadError && (
          <div className="absolute inset-0 z-[2000] flex items-center justify-center bg-white/90">
            <p className="text-sm text-red-500">Failed to load Harvey data: {loadError}</p>
          </div>
        )}

        <LeftPanel sceneOptions={sceneOptions} basemap={basemap} setBasemap={setBasemap} />
        <GeoMapWorkspace sceneOptions={sceneOptions} basemap={basemap} />
        <RightPanel />
      </div>
    </div>
  );
}
