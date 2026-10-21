import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { Database, FlaskConical, History, Moon, Sun } from "lucide-react";
import { NavLink } from "react-router-dom";
import { api } from "../lib/api";
import { useTheme } from "../lib/theme";
import { Dot } from "./ui";

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-7 text-cobalt" aria-hidden>
      <path d="M16 3 27.3 9.5v13L16 29 4.7 22.5v-13Z" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" />
      <circle cx="16" cy="16" r="5.2" fill="none" stroke="currentColor" strokeWidth="2.4" />
    </svg>
  );
}

const NAV = [
  { to: "/", label: "New analysis", icon: FlaskConical, end: true },
  { to: "/history", label: "History", icon: History, end: false },
  { to: "/data", label: "Data", icon: Database, end: false },
];

export function Rail() {
  const { theme, toggle } = useTheme();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const h = health.data;

  return (
    <aside className="md:fixed md:inset-y-0 md:left-0 md:w-56 border-b md:border-b-0 md:border-r border-rule bg-surface flex md:flex-col">
      <div className="flex items-center gap-2.5 px-4 h-14 md:h-16 shrink-0">
        <Logo />
        <div className="font-cond font-semibold leading-[1.1] text-[15px] hidden sm:block">
          Chemical
          <br />
          Price Checker
        </div>
      </div>

      <nav aria-label="Main" className="flex md:flex-col gap-0.5 px-2 md:mt-4 items-center md:items-stretch flex-1 md:flex-none">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-2.5 rounded-md px-2.5 h-9 text-sm transition-colors",
                isActive ? "bg-cobalt-soft text-cobalt font-medium" : "text-slate hover:text-ink hover:bg-paper",
              )
            }
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            <span className="hidden sm:inline">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="md:mt-auto flex md:flex-col items-center md:items-stretch gap-3 px-3 md:px-4 md:pb-5">
        {h && (
          <ul className="hidden md:block space-y-1.5 text-xs text-slate border-t border-rule pt-4" aria-label="Service status">
            <li className="flex items-center gap-2">
              <Dot tone={h.live_scraping ? "fits" : "neutral"} />
              Live vendor search {h.live_scraping ? "on" : "off"}
            </li>
            <li className="flex items-center gap-2">
              <Dot tone={h.llm_enabled ? "fits" : "neutral"} />
              Claude {h.llm_enabled ? "connected" : "not configured"}
            </li>
            <li className="flex items-center gap-2">
              <Dot tone={h.route_prediction ? "fits" : "neutral"} />
              Route prediction {h.route_prediction ? "on" : "off"}
            </li>
          </ul>
        )}
        <button
          type="button"
          onClick={toggle}
          className="flex items-center gap-2 text-sm text-slate hover:text-ink rounded-md h-9 px-2 md:px-0 cursor-pointer"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
          <span className="hidden md:inline">{theme === "dark" ? "Light theme" : "Dark theme"}</span>
        </button>
      </div>
    </aside>
  );
}
