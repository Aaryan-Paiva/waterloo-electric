"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_H = 44;

const INK = "#1D2320", PAPER = "#FBF7EE", AMB = "#F2A72E";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";

const TABS: [string, string][] = [
  ["/", "Home"],
  ["/sandbox", "Product"],
  ["/how-it-works", "How it works"],
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header
      style={{ height: NAV_H, background: INK, borderBottom: "1px solid #2C332D", position: "sticky", top: 0, zIndex: 200, flexShrink: 0, whiteSpace: "nowrap", overflow: "hidden" }}
      className="flex items-center justify-between px-3 sm:px-6"
    >
      <Link href="/" style={{ fontFamily: FD, fontWeight: 700, color: PAPER, display: "flex", alignItems: "center", gap: 7, whiteSpace: "nowrap" }} className="text-xs sm:text-[15px] shrink-0">
        <span style={{ width: 8, height: 8, borderRadius: 3, background: AMB, display: "inline-block", flexShrink: 0 }} />
        Waterloo Electric
      </Link>
      <nav className="flex items-center gap-0.5 sm:gap-1 shrink-0">
        {TABS.map(([href, label]) => {
          const active = href === "/" ? pathname === "/" : pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              style={{
                fontFamily: FD,
                fontWeight: 600,
                color: active ? INK : "#C9C2AE",
                background: active ? AMB : "transparent",
                transition: "background .15s, color .15s",
                whiteSpace: "nowrap",
              }}
              className="text-[11px] sm:text-[13px] px-2.5 sm:px-3.5 py-1.5 rounded-full"
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
