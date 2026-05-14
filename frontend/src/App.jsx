import { AppProvider, useAppContext } from "./context/AppContext.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import MapWorkspace from "./pages/MapWorkspace.jsx";
import MetricsPage from "./pages/MetricsPage.jsx";
import DatasetsPage from "./pages/DatasetsPage.jsx";
import SidebarNav from "./components/SidebarNav.jsx";

const AppContent = () => {
  const { currentPage } = useAppContext();

  if (currentPage === "landing") return <LandingPage />;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <SidebarNav />
      {currentPage === "overview"  && <OverviewPage />}
      {currentPage === "map"       && <MapWorkspace />}
      {currentPage === "metrics"   && <MetricsPage />}
      {currentPage === "datasets"  && <DatasetsPage />}
    </div>
  );
};

const App = () => (
  <AppProvider>
    <AppContent />
  </AppProvider>
);

export default App;