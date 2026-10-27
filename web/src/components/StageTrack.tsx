import clsx from "clsx";
import { Check } from "lucide-react";
import type { StageName } from "../lib/types";

export const STAGES: { name: StageName; label: string; detail: string }[] = [
  { name: "RESOLVE", label: "Identify the compound", detail: "Name, CAS or structure to one record" },
  { name: "CHECK_MARKET", label: "Check vendors", detail: "Cached prices, then live search" },
  { name: "FIND_KNOWN_ROUTE", label: "Look for a known route", detail: "Recorded reactions" },
  { name: "SEARCH_LITERATURE", label: "Search the literature", detail: "Published syntheses (Valency)" },
  { name: "PREDICT_ROUTE", label: "Predict a route", detail: "AiZynthFinder retrosynthesis" },
  { name: "PRICE_MATERIALS", label: "Price starting materials", detail: "Amounts adjusted for yield" },
  { name: "COST", label: "Compare with budget", detail: "Buy against make" },
  { name: "EXPLAIN", label: "Write the summary", detail: "Plain-language verdict" },
];

export type StageStatus = "waiting" | "active" | "done" | "skipped";

/** The pipeline is a real sequence, so the steps are numbered. */
export function StageTrack({
  status,
  seconds,
}: {
  status: Partial<Record<StageName, StageStatus>>;
  seconds: Partial<Record<StageName, number>>;
}) {
  return (
    <ol className="relative">
      {STAGES.map((s, i) => {
        const st = status[s.name] ?? "waiting";
        return (
          <li key={s.name} className="relative flex gap-4 pb-5 last:pb-0">
            {i < STAGES.length - 1 && (
              <span
                aria-hidden
                className={clsx("absolute left-[13px] top-7 bottom-0 w-px", st === "done" ? "bg-cobalt" : "bg-rule")}
              />
            )}
            <span
              className={clsx(
                "relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium tnum",
                st === "done" && "border-cobalt bg-cobalt text-cobalt-ink",
                st === "active" && "border-cobalt text-cobalt bg-surface",
                st === "waiting" && "border-rule text-faint bg-surface",
                st === "skipped" && "border-dashed border-rule text-faint bg-paper",
              )}
            >
              {st === "done" ? <Check className="size-3.5" aria-hidden /> : i + 1}
              {st === "active" && <span className="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-cobalt pulse" aria-hidden />}
            </span>
            <div className="pt-0.5 min-w-0">
              <div className={clsx("text-sm font-medium", st === "waiting" || st === "skipped" ? "text-slate" : "text-ink")}>
                {s.label}
                <span className="sr-only">: {st}</span>
              </div>
              <div className="text-xs text-slate">
                {st === "skipped" ? "Not needed for this compound" : st === "done" && seconds[s.name] != null ? `${s.detail}, ${seconds[s.name]!.toFixed(1)} s` : s.detail}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
