import { useAppContext } from "../context/AppContext.jsx";

const NAV_ITEMS = [
  {
    id: "overview",
    label: "Overview",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
      </svg>
    ),
  },
  {
    id: "map",
    label: "Map View",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/>
      </svg>
    ),
  },
  {
    id: "metrics",
    label: "Metrics",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>
      </svg>
    ),
  },
  {
    id: "datasets",
    label: "VLM Analysis",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M20 6h-2.18c.07-.44.18-.88.18-1.36C18 2.53 15.47 0 12.36 0c-1.71 0-3.25.73-4.32 1.9L7 3 5.96 1.9C4.89.73 3.34 0 1.63 0-.55 0-2 1.53-2 3.64c0 .48.1.92.18 1.36H-2c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h22c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-7.64-3.36c.52-.55 1.24-.87 2-.87 1.47 0 2.64 1.17 2.64 2.59 0 .48-.17.93-.41 1.64H12V3.64c0-.3.12-.58.36-.99zM4 2.77c0-1.42 1.17-2.59 2.64-2.59.76 0 1.48.32 2 .87.24.41.36.69.36.99V6H4.41C4.17 5.29 4 4.84 4 4.36V2.77zM20 20H2V8h18v12z"/>
      </svg>
    ),
  },
];

export default function SidebarNav() {
  const { currentPage, setCurrentPage } = useAppContext();

  return (
    <aside className="w-16 flex flex-col bg-white border-r border-gray-100 shrink-0 py-4 items-center gap-1">
      {/* Logo */}
      <button
        onClick={() => setCurrentPage("landing")}
        title="Home"
        className="mb-4 w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center hover:bg-blue-700 transition-colors"
      >
        <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </button>

      {/* Nav items */}
      <nav className="flex flex-col gap-1 flex-1 w-full px-2">
        {NAV_ITEMS.map((item) => {
          const active = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentPage(item.id)}
              title={item.label}
              className={`relative flex flex-col items-center justify-center w-full py-2.5 rounded-xl transition-all group ${
                active
                  ? "bg-blue-50 text-blue-600"
                  : "text-gray-400 hover:bg-gray-50 hover:text-gray-700"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-blue-600 rounded-r-full" />
              )}
              {item.icon}
              <span className="text-[9px] font-medium mt-0.5 leading-none">{item.label}</span>
            </button>
          );
        })}
      </nav>

    </aside>
  );
}
