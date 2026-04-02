/**
 * Harvey dataset adapter — scene-first API.
 *
 * Primary model: scenes identified by sceneId.
 * Pre/post imagery modes are driven by selectedSceneId.
 * Flat marker arrays (preMarkers, postMarkers) are kept for future overlay use.
 */

let _cache = null;

export async function loadHarveyData() {
  if (_cache) return _cache;
  const res = await fetch("/harvey/harvey-data.json");
  if (!res.ok) throw new Error("Failed to load Harvey data");
  _cache = await res.json();
  return _cache;
}

// ─── Scene-first helpers ────────────────────────────────────────────────────

/** Find a scene by its sceneId string. Primary lookup for imagery modes. */
export function findSceneById(data, sceneId) {
  return data.scenes.find((s) => s.sceneId === sceneId) ?? null;
}

/**
 * Returns the sorted list of all scenes as selector-friendly option objects.
 * Each entry has: { sceneId, label, shortId, preDate, postDate, centroid, buildingCount }
 */
export function getSceneOptions(data) {
  return data.scenes.map((s) => {
    const shortId = parseInt(s.sceneId, 10);
    const preDate = s.captureDate?.pre
      ? new Date(s.captureDate.pre).toLocaleDateString("en-US", { month: "short", year: "numeric" })
      : null;
    const postDate = s.captureDate?.post
      ? new Date(s.captureDate.post).toLocaleDateString("en-US", { month: "short", year: "numeric" })
      : null;
    return {
      sceneId: s.sceneId,
      shortId,
      label: `Scene #${shortId}`,
      preDate,
      postDate,
      centroid: s.centroid,
      buildingCount: s.buildingCount,
    };
  });
}

/**
 * Returns rich metadata for a single scene — used to drive the imagery workspace
 * and the scene metadata panel.
 */
export function getScenePreview(data, sceneId) {
  const s = findSceneById(data, sceneId);
  if (!s) return null;
  const fmt = (iso) =>
    iso ? new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) : "—";
  return {
    sceneId: s.sceneId,
    shortId: parseInt(s.sceneId, 10),
    disaster: s.disaster,
    disasterType: s.disasterType,
    preImagePath: s.imagePath?.pre ?? null,
    postImagePath: s.imagePath?.post ?? null,
    preDate: fmt(s.captureDate?.pre),
    postDate: fmt(s.captureDate?.post),
    centroid: s.centroid,
    buildingCount: s.buildingCount,
  };
}

/**
 * Returns scene centroid markers for the overlay map.
 * Each entry: { sceneId, shortId, lat, lng }
 */
export function getSceneCentroids(data) {
  return data.scenes
    .filter((s) => s.centroid)
    .map((s) => ({
      sceneId: s.sceneId,
      shortId: parseInt(s.sceneId, 10),
      lat: s.centroid.lat,
      lng: s.centroid.lng,
    }));
}

// ─── Overlay/future backend helpers ─────────────────────────────────────────

/** Get all building markers for a given phase ("pre" | "post"). For overlay/future use. */
export function getMarkersByPhase(data, phase) {
  return phase === "pre" ? data.preMarkers : data.postMarkers;
}

// ─── Damage display constants ────────────────────────────────────────────────

export const DAMAGE_COLOR = {
  destroyed: "#ef4444",
  major: "#f97316",
  minor: "#eab308",
  none: "#22c55e",
};

export const DAMAGE_LABEL = {
  destroyed: "Destroyed",
  major: "Major Damage",
  minor: "Minor Damage",
  none: "No Damage",
};
