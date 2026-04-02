import { useState, useEffect, useRef, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { useAppContext } from "../context/AppContext.jsx";
import { postQuery } from "../services/api.js";
import {
  loadHarveyData,
  getSceneOptions,
  getScenePreview,
  getSceneCentroids,
  DAMAGE_COLOR,
  DAMAGE_LABEL,
} from "../data/harveyAdapter.js";

const MAP_CENTER = [29.758, -95.367];
const MAP_ZOOM = 11;

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

  // Scroll selected item into view when scene changes externally
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

function OverlayLayerControls() {
  const { opacity, setOpacity } = useAppContext();
  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Marker Opacity</p>
          <span className="text-xs font-medium text-gray-600">{opacity}%</span>
        </div>
        <input type="range" min={0} max={100} value={opacity}
          onChange={(e) => setOpacity(Number(e.target.value))}
          className="w-full accent-blue-600" />
      </div>

      {/* VLM integration placeholder */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-3 space-y-1.5">
        <div className="flex items-center gap-1.5">
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5 text-amber-500 shrink-0"><path d="M12 2a10 10 0 100 20A10 10 0 0012 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          <p className="text-[11px] font-semibold text-amber-700">VLM Damage Overlay</p>
        </div>
        <p className="text-[10px] text-amber-600 leading-snug">
          Connect backend to activate damage classification on the map. Scene locations are shown as placeholders.
        </p>
      </div>
    </div>
  );
}

function LeftPanel({ sceneOptions, isImageryMode }) {
  return (
    <div className="w-64 shrink-0 bg-white border-r border-gray-100 flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 shrink-0">
        <h2 className="font-semibold text-gray-900 text-sm">Layer Control</h2>
      </div>
      <div className={`flex flex-col px-4 py-4 space-y-5 text-sm ${isImageryMode ? "flex-1 min-h-0 overflow-hidden" : "overflow-y-auto"}`}>
        <ModeToggle />
        {isImageryMode
          ? <HarveySceneSelector sceneOptions={sceneOptions} />
          : <OverlayLayerControls />
        }
      </div>
    </div>
  );
}

// ─── Pre/Post: Scene Image Workspace ─────────────────────────────────────────

function SceneImageWorkspace({ sceneOptions }) {
  const { imageryLayer, setImageryLayer, selectedSceneId, setSelectedSceneId, harveyData } = useAppContext();

  const preview = useMemo(
    () => (harveyData && selectedSceneId ? getScenePreview(harveyData, selectedSceneId) : null),
    [harveyData, selectedSceneId]
  );

  const imgSrc = imageryLayer === "pre" ? preview?.preImagePath : preview?.postImagePath;
  const imgDate = imageryLayer === "pre" ? preview?.preDate : preview?.postDate;

  // Navigate to prev/next scene
  const currentIdx = sceneOptions.findIndex((s) => s.sceneId === selectedSceneId);
  const prevScene = currentIdx > 0 ? sceneOptions[currentIdx - 1] : null;
  const nextScene = currentIdx < sceneOptions.length - 1 ? sceneOptions[currentIdx + 1] : null;

  const goTo = (s) => { if (s) setSelectedSceneId(s.sceneId); };

  // Keyboard navigation
  useEffect(() => {
    const prev = prevScene;
    const next = nextScene;
    const handler = (e) => {
      if (e.key === "ArrowLeft") { if (prev) setSelectedSceneId(prev.sceneId); }
      if (e.key === "ArrowRight") { if (next) setSelectedSceneId(next.sceneId); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [prevScene, nextScene, setSelectedSceneId]);

  if (!selectedSceneId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-gray-950 text-gray-500 select-none">
        <svg viewBox="0 0 24 24" fill="currentColor" className="w-12 h-12 mb-4 text-gray-700"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
        <p className="text-sm">Select a scene from the left panel</p>
        <p className="text-xs text-gray-600 mt-1">{sceneOptions.length} Harvey scenes available</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-gray-950 overflow-hidden relative">
      {/* Top bar */}
      <div className="shrink-0 flex items-center justify-between px-5 py-2.5 bg-gray-900/80 backdrop-blur border-b border-white/5">
        <div className="flex items-center gap-3">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${imageryLayer === "pre" ? "bg-blue-500/20 text-blue-300 border border-blue-500/30" : "bg-orange-500/20 text-orange-300 border border-orange-500/30"}`}>
            {imageryLayer}-disaster
          </span>
          <span className="text-sm font-semibold text-white">Scene #{preview?.shortId}</span>
          {imgDate && <span className="text-xs text-gray-400">{imgDate}</span>}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span>{preview?.disaster?.replace(/-/g, " ")}</span>
          <span className="text-gray-600">·</span>
          <span>{currentIdx + 1} / {sceneOptions.length}</span>
        </div>
      </div>

      {/* Main image */}
      <div className="flex-1 flex items-center justify-center relative overflow-hidden">
        {imgSrc ? (
          <img
            key={imgSrc}
            src={imgSrc}
            alt={`${imageryLayer}-disaster scene ${preview?.shortId}`}
            className="max-w-full max-h-full object-contain select-none"
            draggable={false}
          />
        ) : (
          <div className="text-center space-y-2">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10 text-gray-700 mx-auto"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
            <p className="text-sm text-gray-500">No {imageryLayer}-disaster image</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="shrink-0 flex items-center justify-between px-5 py-3 bg-gray-900/80 backdrop-blur border-t border-white/5">
        <button onClick={() => goTo(prevScene)} disabled={!prevScene}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z"/></svg>
          {prevScene ? `Scene #${prevScene.shortId}` : "Previous"}
        </button>
        <div className="flex gap-1">
          {["pre", "post"].map((p) => (
            <button key={p} onClick={() => setImageryLayer(p)}
              className={`text-[10px] font-bold px-2.5 py-1 rounded uppercase tracking-wider transition-colors ${imageryLayer === p ? "bg-blue-600 text-white" : "text-gray-500 hover:text-gray-300"}`}>
              {p}
            </button>
          ))}
        </div>
        <button onClick={() => goTo(nextScene)} disabled={!nextScene}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
          {nextScene ? `Scene #${nextScene.shortId}` : "Next"}
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Overlay: Leaflet Map Workspace ─────────────────────────────────────────

function ResetView() {
  const map = useMap();
  useEffect(() => { map.setView(MAP_CENTER, MAP_ZOOM); }, [map]);
  return null;
}

function OverlayMapWorkspace() {
  const { harveyData, selectedSceneId, setSelectedSceneId, opacity } = useAppContext();

  const sceneCentroids = useMemo(
    () => (harveyData ? getSceneCentroids(harveyData) : []),
    [harveyData]
  );

  const markerOpacity = opacity / 100;

  return (
    <div className="flex-1 relative">
      <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} className="w-full h-full" zoomControl>
        <ResetView />
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        {sceneCentroids.map((sc) => {
          const isSelected = sc.sceneId === selectedSceneId;
          return (
            <CircleMarker
              key={sc.sceneId}
              center={[sc.lat, sc.lng]}
              radius={isSelected ? 10 : 7}
              pathOptions={{
                fillColor: isSelected ? "#2563eb" : "#60a5fa",
                color: "white",
                weight: isSelected ? 2.5 : 1.5,
                fillOpacity: (isSelected ? 0.95 : 0.7) * markerOpacity,
              }}
              eventHandlers={{ click: () => setSelectedSceneId(sc.sceneId) }}>
              <Tooltip direction="top" offset={[0, -10]} opacity={0.95}>
                <div className="text-xs">
                  <div className="font-semibold">Scene #{sc.shortId}</div>
                  <div className="text-gray-500">Click to select</div>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Scene count badge */}
      {harveyData && (
        <div className="absolute top-3 right-3 z-[1000] bg-white rounded-lg shadow border border-gray-100 px-3 py-2 text-xs text-gray-600">
          <span className="font-semibold text-gray-800">{sceneCentroids.length}</span> scene locations
        </div>
      )}

      {/* VLM placeholder notice */}
      <div className="absolute bottom-5 left-5 z-[1000] bg-white rounded-xl shadow-lg border border-amber-200 p-3 text-xs max-w-[200px]">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
          <p className="font-semibold text-gray-700">Overlay Mode</p>
        </div>
        <p className="text-gray-500 leading-snug">Scene locations only. VLM damage overlay activates when backend is connected.</p>
      </div>
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
          <div className="flex gap-2"><span className="w-20 shrink-0 text-gray-400">Location</span><span className="text-gray-700 font-mono text-[10px]">{preview.centroid.lat.toFixed(4)}, {preview.centroid.lng.toFixed(4)}</span></div>
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
            <div className={`rounded-lg overflow-hidden bg-gray-100 aspect-square ring-2 transition-all ${imageryLayer === "post" ? "ring-orange-500" : "ring-transparent"}`}>
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
  const { rightTab, setRightTab, imageryLayer } = useAppContext();
  const detailLabel = imageryLayer === "overlay" ? "Scene Details" : "Scene Details";
  return (
    <div className="w-72 shrink-0 bg-white border-l border-gray-100 flex flex-col">
      <div className="flex border-b border-gray-100 shrink-0">
        {[{ id: "details", label: detailLabel }, { id: "assistant", label: "AI Assistant" }].map((tab) => (
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

  // Load Harvey data once
  useEffect(() => {
    if (harveyData) return;
    loadHarveyData()
      .then((data) => {
        setHarveyData(data);
        // Default to first scene
        if (data.scenes.length > 0) setSelectedSceneId(data.scenes[0].sceneId);
      })
      .catch((e) => setLoadError(e.message));
  }, [harveyData, setHarveyData, setSelectedSceneId]);

  const sceneOptions = useMemo(
    () => (harveyData ? getSceneOptions(harveyData) : []),
    [harveyData]
  );

  const isImageryMode = imageryLayer === "pre" || imageryLayer === "post";

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
          {[{ label: isImageryMode ? "Imagery View" : "Map View", active: true }, { label: "Export Report", active: false }].map((btn) => (
            <button key={btn.label}
              className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${btn.active ? "bg-blue-600 text-white" : "border border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              {btn.label}
            </button>
          ))}
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

        <LeftPanel sceneOptions={sceneOptions} isImageryMode={isImageryMode} />

        {isImageryMode
          ? <SceneImageWorkspace sceneOptions={sceneOptions} />
          : <OverlayMapWorkspace />
        }

        <RightPanel />
      </div>
    </div>
  );
}
