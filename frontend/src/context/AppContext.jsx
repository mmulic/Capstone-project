import { createContext, useContext, useState } from "react";

const AppContext = createContext(null);

export const AppProvider = ({ children }) => {
  const [currentPage, setCurrentPage] = useState("landing"); // landing | overview | map | metrics | settings
  const [imageryLayer, setImageryLayer] = useState("overlay"); // pre | post | overlay

  // Harvey dataset — loaded once in MapWorkspace, stored here so it survives navigation
  const [harveyData, setHarveyData] = useState(null);

  // Scene selection — the primary shared state for pre/post imagery and overlay map
  // Initialized to null; set to the first available scene once data loads
  const [selectedSceneId, setSelectedSceneId] = useState(null);

  // Overlay map controls
  const [opacity, setOpacity] = useState(75);
  const [damageFilters, setDamageFilters] = useState({
    destroyed: true,
    major: true,
    minor: false,
    none: false,
  });
  const [aiConfidence, setAiConfidence] = useState(85);

  // Right panel
  const [rightTab, setRightTab] = useState("details"); // details | assistant
  const [chatHistory, setChatHistory] = useState([]);

  // Legacy/future overlay property selection (kept for backward compat and overlay interactions)
  const [selectedProperty, setSelectedProperty] = useState(null);

  const [loading, setLoading] = useState(false);

  return (
    <AppContext.Provider value={{
      currentPage, setCurrentPage,
      imageryLayer, setImageryLayer,
      harveyData, setHarveyData,
      selectedSceneId, setSelectedSceneId,
      opacity, setOpacity,
      damageFilters, setDamageFilters,
      aiConfidence, setAiConfidence,
      rightTab, setRightTab,
      chatHistory, setChatHistory,
      selectedProperty, setSelectedProperty,
      loading, setLoading,
    }}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be inside AppProvider");
  return ctx;
};
