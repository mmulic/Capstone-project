/**
 * Harvey dataset adapter — scene-first API.
 *
 * Primary model: scenes identified by sceneId.
 * Pre/post imagery modes are driven by selectedSceneId.
 * Flat marker arrays (preMarkers, postMarkers) are kept for future overlay use.
 */

import { getScenesWithPredictions } from "../services/api.js";

let _cache = null;

const HARVEY_DISASTER = "hurricane-harvey";

export async function loadHarveyData() {
  if (_cache) return _cache;
  const res = await fetch("/harvey/harvey-data.json");
  if (!res.ok) throw new Error("Failed to load Harvey data");
  const raw = await res.json();

  const harveySceneIds = new Set(
    raw.scenes.filter(s => s.disaster === HARVEY_DISASTER).map(s => s.sceneId)
  );

  // Fetch scene IDs that have predictions in Supabase — drop the rest
  let scenesWithPredictions = new Set();
  try {
    const ids = await getScenesWithPredictions();
    ids.forEach(id => {
      // API returns full scene_id like "hurricane-harvey_00000003", extract the numeric part
      const shortId = id.replace("hurricane-harvey_", "");
      scenesWithPredictions.add(shortId);
    });
  } catch {
    // If the API is unreachable, fall back to showing all scenes
    scenesWithPredictions = harveySceneIds;
  }

  // Drop zero-building scenes and scenes without predictions
  const placeableIds = new Set(
    raw.scenes
      .filter(s => harveySceneIds.has(s.sceneId))
      .filter(s => (s.buildingCount?.pre ?? 0) + (s.buildingCount?.post ?? 0) > 0)
      .filter(s => scenesWithPredictions.has(s.sceneId))
      .map(s => s.sceneId)
  );

  _cache = {
    scenes:      raw.scenes.filter(s => placeableIds.has(s.sceneId)),
    preMarkers:  raw.preMarkers.filter(m => placeableIds.has(m.sceneId)),
    postMarkers: raw.postMarkers.filter(m => placeableIds.has(m.sceneId)),
  };
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

// ─── Image overlay helpers ────────────────────────────────────────────────────

/**
 * Returns an array of image overlay descriptors for all scenes that have
 * a valid image and geographic bounds for the given phase ("pre" | "post").
 * Each entry: { sceneId, url, bounds: [[lat_sw, lng_sw], [lat_ne, lng_ne]] }
 */
export function getSceneImageOverlays(data, phase) {
  return data.scenes
    .filter((s) => s.imagePath?.[phase] && s.imageBounds)
    .map((s) => ({
      sceneId: s.sceneId,
      url: s.imagePath[phase],
      bounds: [s.imageBounds.sw, s.imageBounds.ne],
    }));
}

// ─── Overlay/polygon helpers ─────────────────────────────────────────────────

/** Get all building markers for a given phase ("pre" | "post"). For overlay/future use. */
export function getMarkersByPhase(data, phase) {
  return phase === "pre" ? data.preMarkers : data.postMarkers;
}

/**
 * Returns a Set of building UIDs belonging to a scene (from postMarkers).
 * Used to filter backend predictions to only those in the selected scene.
 */
export function getSceneBuildingUids(data, sceneId) {
  return new Set(
    (data.postMarkers ?? [])
      .filter((m) => m.sceneId === sceneId)
      .map((m) => m.uid)
  );
}

/**
 * Lazily fetches the pre-built polygon map for a scene.
 * Returns { uid: [[lat, lng], ...] } — an empty object if the file is missing.
 */
export async function loadScenePolygons(sceneId) {
  try {
    const res = await fetch(`/harvey/scene-polygons/${sceneId}.json`);
    if (!res.ok) return {};
    return res.json();
  } catch {
    return {};
  }
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
