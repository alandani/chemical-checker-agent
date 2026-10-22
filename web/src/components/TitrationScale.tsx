import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import type { CostBreakdown } from "../lib/types";
import { money, moneyRound } from "../lib/format";

function niceStep(max: number, target: number): number {
  const raw = max / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return step * mag;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(800);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return { ref, width };
}

interface Reading {
  key: "buy" | "make";
  label: string;
  value: number;
  cheapest: boolean;
  incomplete: boolean;
}

const LABEL_PX = 170; // room one reading label needs before the next one must stack
const ROW_PX = 44;

/**
 * The budget drawn as a titration endpoint: an indicator strip that is green
 * below the budget and magenta above it, with "buy" and "make" plotted as readings.
 */
export function TitrationScale({ cost }: { cost: CostBreakdown }) {
  const { ref, width } = useWidth<HTMLDivElement>();

  const readings: Reading[] = [];
  if (cost.buy)
    readings.push({ key: "buy", label: "Buy", value: cost.buy.total_aud, cheapest: cost.cheapest === "buy", incomplete: false });
  if (cost.make_total_aud != null)
    readings.push({
      key: "make",
      label: cost.make_complete ? "Make" : "Make (some prices missing)",
      value: cost.make_total_aud,
      cheapest: cost.cheapest === "make",
      incomplete: !cost.make_complete,
    });

  const budget = cost.budget_aud;
  const top = Math.max(budget, ...readings.map((r) => r.value), 1) * 1.15;
  const step = niceStep(top, width < 520 ? 3 : 6);
  const max = Math.ceil(top / step) * step;
  const pct = (v: number) => Math.min(100, (v / max) * 100);
  const ticks: number[] = [];
  for (let t = 0; t <= max + 1e-9; t += step) ticks.push(t);

  // Stack labels that would collide at the current width.
  const sorted = [...readings].sort((a, b) => a.value - b.value);
  const row: Record<string, number> = {};
  sorted.forEach((r, i) => {
    const prev = sorted[i - 1];
    const gapPx = prev ? ((r.value - prev.value) / max) * width : Infinity;
    row[r.key] = gapPx < LABEL_PX ? 1 - row[prev!.key] : 0;
  });
  const rows = Math.max(1, ...Object.values(row).map((r) => r + 1));
  const labelArea = rows * ROW_PX + 8;
  const stripY = labelArea; // top of the indicator strip
  const budgetPct = pct(budget);

  return (
    <figure className="select-none" aria-label={`Cost compared with a budget of ${money(budget)}`}>
      <div ref={ref} className="relative mx-1" style={{ height: stripY + 58 }}>
        {/* indicator strip: green below the budget, magenta above */}
        <div className="absolute left-0 right-0 h-3.5 rounded-sm overflow-hidden flex" style={{ top: stripY }}>
          <div className="h-full bg-fits-soft transition-[width] duration-700" style={{ width: `${budgetPct}%` }} />
          <div className="h-full flex-1 bg-over-soft" />
        </div>

        {/* readings */}
        {readings.map((r) => {
          const over = r.value > budget;
          const p = pct(r.value);
          const alignRight = p > 70;
          const labelTop = (rows - 1 - row[r.key]) * ROW_PX;
          return (
            <div key={r.key} className="absolute top-0 bottom-0 transition-[left] duration-700 ease-out" style={{ left: `${p}%` }}>
              <div
                className={clsx("absolute left-0 w-px", over ? "bg-over" : "bg-fits", r.incomplete && "opacity-50")}
                style={{ top: labelTop + 6, height: stripY - labelTop - 6 }}
              />
              <div
                className={clsx("absolute whitespace-nowrap leading-tight", alignRight ? "right-0 text-right pr-2" : "left-0 pl-2")}
                style={{ top: labelTop }}
              >
                <div className={clsx("text-xs", r.cheapest ? "text-ink font-medium" : "text-slate")}>
                  {r.cheapest && readings.length > 1 ? `${r.label}, the cheaper option` : r.label}
                </div>
                <div className={clsx("font-cond tnum text-lg font-semibold", over ? "text-over" : "text-fits")}>{money(r.value)}</div>
              </div>
              <div
                aria-hidden
                className={clsx(
                  "absolute -ml-[9px] size-[18px] rounded-full border-2",
                  over ? "border-over" : "border-fits",
                  r.cheapest ? (over ? "bg-over" : "bg-fits") : "bg-surface",
                  r.incomplete && "border-dashed",
                )}
                style={{ top: stripY - 2 }}
              />
            </div>
          );
        })}

        {/* budget endpoint */}
        <div
          className="absolute w-[2px] -ml-px bg-ink transition-[left] duration-700"
          style={{ left: `${budgetPct}%`, top: stripY - 14, height: 44 }}
        />
        <div
          className={clsx(
            "absolute whitespace-nowrap text-xs font-medium transition-[left] duration-700",
            budgetPct > 75 ? "-translate-x-full pr-1.5" : "pl-1.5",
          )}
          style={{ left: `${budgetPct}%`, top: stripY + 22 }}
        >
          Budget {moneyRound(budget)}
        </div>

        {/* axis */}
        <div className="absolute left-0 right-0 h-px bg-rule" style={{ top: stripY + 22 }} />
        {ticks.map((t) => {
          const near = Math.abs(t - budget) / max < (width < 520 ? 0.2 : 0.09);
          return (
            <div key={t} className="absolute" style={{ left: `${(t / max) * 100}%`, top: stripY + 20 }}>
              <div className="absolute h-1.5 w-px bg-rule" />
              {!near && (
                <span className="absolute top-3.5 -translate-x-1/2 text-[11px] text-faint tnum whitespace-nowrap">{moneyRound(t)}</span>
              )}
            </div>
          );
        })}
      </div>
      {readings.length === 0 && (
        <figcaption className="text-sm text-slate mt-2">No complete price yet, so there's nothing to plot against the budget.</figcaption>
      )}
    </figure>
  );
}
