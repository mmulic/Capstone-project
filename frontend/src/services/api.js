import axios from "axios";

// In production nginx proxies /api/, /query, /damage-data, etc. to the backend.
// VITE_API_BASE_URL can override (e.g. for local dev pointing at a remote server).
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error("[API Error]", err.response?.status, err.message);
    return Promise.reject(err);
  }
);

/** GET /damage-data → GeoJSON FeatureCollection of assessed properties */
export async function getDamageData(params = {}) {
  const { data } = await api.get("/damage-data", { params });
  return data;
}

/** POST /query → { message, history } → AI assistant response */
export async function postQuery(message, history = []) {
  const { data } = await api.post("/query", { message, history });
  return data;
}

/** GET /evaluate?propertyId=X → single property evaluation */
export async function evaluateProperty(propertyId) {
  const { data } = await api.get("/evaluate", { params: { propertyId } });
  return data;
}

/**
 * GET /api/ml/stats
 * Returns damage distribution grouped by disaster.
 * Shape: { by_disaster, overall_distribution, total_predictions, disasters_count }
 */
export async function getMLStats() {
  const { data } = await api.get("/api/ml/stats");
  return data;
}

/**
 * GET /api/ml/evaluation
 * Returns model evaluation metrics (accuracy, precision, recall, F1, confusion matrix).
 * Returns null if no evaluation runs exist yet.
 */
export async function getMLEvaluation(jobId) {
  const { data } = await api.get("/api/ml/evaluation", {
    params: jobId ? { job_id: jobId } : {},
  });
  return data;
}

/**
 * POST /api/vlm/analyze — Send a pre/post image pair to Gemini for per-building
 * damage assessment. When preImage is provided, Gemini runs in comparison mode
 * (before vs after) for more accurate damage classification.
 * Content-Type is left unset so axios attaches the multipart boundary automatically.
 */
export async function analyzeScene(postImage, preImage = null) {
  const formData = new FormData();
  formData.append("post_image", postImage);
  if (preImage) {
    formData.append("pre_image", preImage);
  }

  const { data } = await api.post("/api/vlm/analyze", formData, {
    headers: { "Content-Type": undefined },
    timeout: 120000,
  });
  return data;
}

export default api;
