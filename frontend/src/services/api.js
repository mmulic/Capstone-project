import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
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

export default api;
