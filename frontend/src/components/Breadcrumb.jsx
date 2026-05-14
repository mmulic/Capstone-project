import { useAppContext } from "../context/AppContext.jsx";

const Chevron = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3 text-gray-300 shrink-0">
    <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
  </svg>
);

/**
 * Breadcrumb — renders a navigable crumb trail.
 *
 * Props:
 *   crumbs: Array of { label, page? }
 *     - If `page` is provided the crumb is clickable and navigates to that page.
 *     - The last crumb is always rendered as plain text (current page).
 *
 * Example:
 *   <Breadcrumb crumbs={[
 *     { label: "Home",             page: "landing"  },
 *     { label: "Hurricane Harvey", page: "overview" },
 *     { label: "Damage Overlay" },
 *   ]} />
 */
const Breadcrumb = ({ crumbs = [] }) => {
  const { setCurrentPage } = useAppContext();

  return (
    <nav className="flex items-center gap-1.5 text-sm text-gray-400">
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <Chevron />}
            {isLast || !crumb.page ? (
              <span className={isLast ? "text-gray-800 font-medium" : "text-gray-400"}>
                {crumb.label}
              </span>
            ) : (
              <button
                onClick={() => setCurrentPage(crumb.page)}
                className="hover:text-blue-600 transition-colors"
              >
                {crumb.label}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
};

export default Breadcrumb;
