import { useState, useRef, useCallback } from "react";
import { analyzeScene } from "../services/api.js";

// ─── Constants ────────────────────────────────────────────────────────────────

const DAMAGE_STYLES = {
  no_damage:    { label: "No Damage",    bg: "bg-green-100",  text: "text-green-800",  dot: "bg-green-400"  },
  minor_damage: { label: "Minor Damage", bg: "bg-yellow-100", text: "text-yellow-800", dot: "bg-yellow-400" },
  major_damage: { label: "Major Damage", bg: "bg-orange-100", text: "text-orange-800", dot: "bg-orange-400" },
  destroyed:    { label: "Destroyed",    bg: "bg-red-100",    text: "text-red-800",    dot: "bg-red-500"    },
};

const DAMAGE_ORDER = ["no_damage", "minor_damage", "major_damage", "destroyed"];

// ─── ImageDropZone ────────────────────────────────────────────────────────────

function ImageDropZone({ label, accent, file, preview, onFile }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFile(dropped);
  }, [onFile]);

  return (
    <div className="flex-1 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className={`w-2.5 h-2.5 rounded-full ${accent}`} />
        <span className="text-sm font-semibold text-gray-700">{label}</span>
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        className={`
          relative h-52 rounded-xl border-2 border-dashed cursor-pointer transition-all
          flex flex-col items-center justify-center overflow-hidden
          ${dragging ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300 hover:bg-gray-50"}
        `}
      >
        {preview ? (
          <>
            <img src={preview} alt={label} className="w-full h-full object-cover rounded-xl" />
            <div className="absolute inset-0 bg-black/0 hover:bg-black/20 transition-all rounded-xl flex items-center justify-center">
              <span className="opacity-0 hover:opacity-100 text-white text-xs font-medium bg-black/60 px-3 py-1 rounded-full">
                Replace
              </span>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-400 p-6">
            <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="text-sm text-center">
              <span className="font-medium text-gray-500">Click to upload</span> or drag & drop
            </p>
            <p className="text-xs text-gray-400">JPEG, PNG, TIFF — max 50 MB</p>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/tiff"
          className="hidden"
          onChange={(e) => { if (e.target.files[0]) onFile(e.target.files[0]); }}
        />
      </div>

      {file && (
        <p className="text-xs text-gray-500 truncate">
          {file.name} — {(file.size / 1024 / 1024).toFixed(2)} MB
        </p>
      )}
    </div>
  );
}

// ─── ResultsPanel ─────────────────────────────────────────────────────────────

function ResultsPanel({ result }) {
  const { buildings_visible, damage_counts, scene_summary, model_used, comparison_mode } = result;

  return (
    <div className="space-y-4">
      {/* Mode badge */}
      {comparison_mode && (
        <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-xl px-4 py-2.5 text-sm text-blue-700">
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0"><path d="M9 3H5c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h4c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 6H5V5h4v4zm10-6h-4c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h4c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 6h-4V5h4v4zM9 13H5c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h4c1.1 0 2-.9 2-2v-4c0-1.1-.9-2-2-2zm0 6H5v-4h4v4zm10-6h-4c-1.1 0-2 .9-2 2v4c0 1.1.9 2 2 2h4c1.1 0 2-.9 2-2v-4c0-1.1-.9-2-2-2zm0 6h-4v-4h4v4z"/></svg>
          <span><span className="font-semibold">Comparison mode</span> — pre vs post images analyzed together for higher accuracy</span>
        </div>
      )}

      {/* Damage count cards */}
      <div className="grid grid-cols-4 gap-3">
        {DAMAGE_ORDER.map((key) => {
          const s = DAMAGE_STYLES[key];
          return (
            <div key={key} className={`rounded-xl p-4 ${s.bg}`}>
              <p className={`text-2xl font-bold ${s.text}`}>{damage_counts[key] ?? 0}</p>
              <p className={`text-xs font-medium mt-0.5 ${s.text} opacity-80`}>{s.label}</p>
            </div>
          );
        })}
      </div>

      {/* Total buildings + summary */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 space-y-2">
        <p className="text-sm text-gray-700">
          <span className="font-semibold">{buildings_visible}</span> building{buildings_visible !== 1 ? "s" : ""} identified in scene
        </p>
        {scene_summary && (
          <p className="text-sm text-gray-500 leading-relaxed">{scene_summary}</p>
        )}
        {model_used && (
          <p className="text-xs text-gray-400">Model: {model_used}{comparison_mode ? " · comparison mode" : ""}</p>
        )}
      </div>
    </div>
  );
}

// ─── DatasetsPage ─────────────────────────────────────────────────────────────

export default function DatasetsPage() {
  const [preFile, setPreFile]         = useState(null);
  const [postFile, setPostFile]       = useState(null);
  const [prePreview, setPrePreview]   = useState(null);
  const [postPreview, setPostPreview] = useState(null);
  const [status, setStatus]           = useState("idle");
  const [result, setResult]           = useState(null);
  const [error, setError]             = useState(null);

  const handleFile = (slot, f) => {
    const url = URL.createObjectURL(f);
    if (slot === "pre") { setPreFile(f); setPrePreview(url); }
    else                { setPostFile(f); setPostPreview(url); }
    setResult(null); setError(null); setStatus("idle");
  };

  const canSubmit = postFile && status !== "analyzing";

  const handleAnalyze = async () => {
    setError(null); setResult(null); setStatus("analyzing");
    try {
      // Pass preFile too — backend uses it for comparison analysis when present
      const data = await analyzeScene(postFile, preFile);
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Something went wrong.");
      setStatus("error");
    }
  };

  const handleReset = () => {
    setPreFile(null); setPostFile(null);
    setPrePreview(null); setPostPreview(null);
    setResult(null); setError(null); setStatus("idle");
  };

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">VLM Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload a pre- and post-disaster image pair. When both images are provided, Gemini compares them for higher-accuracy damage classification (comparison mode). Post-disaster image alone also works.
          </p>
        </div>

        {/* Upload card */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-6">
          <div className="flex gap-6">
            <ImageDropZone
              label="Pre-disaster"
              accent="bg-blue-400"
              file={preFile}
              preview={prePreview}
              onFile={(f) => handleFile("pre", f)}
            />
            <ImageDropZone
              label="Post-disaster"
              accent="bg-orange-400"
              file={postFile}
              preview={postPreview}
              onFile={(f) => handleFile("post", f)}
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleAnalyze}
              disabled={!canSubmit}
              className={`
                flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all
                ${canSubmit
                  ? "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                  : "bg-gray-100 text-gray-400 cursor-not-allowed"}
              `}
            >
              {status === "analyzing" && (
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
              )}
              {status === "analyzing" ? "Analyzing…" : "Run VLM Analysis"}
            </button>

            {(status === "done" || status === "error") && (
              <button
                onClick={handleReset}
                className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-100 transition-all"
              >
                Reset
              </button>
            )}

            {!postFile && <p className="text-xs text-gray-400">Upload a post-disaster image to continue</p>}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            <span className="font-semibold">Error: </span>{error}
          </div>
        )}

        {/* Results */}
        {result && <ResultsPanel result={result} />}

      </div>
    </div>
  );
}
