import clsx from "clsx";
import { useMutation } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CompoundFacts } from "../components/CompoundFacts";
import { RouteSteps } from "../components/RouteSteps";
import { StageTrack } from "../components/StageTrack";
import { Molecule } from "../components/Structure";
import { MaterialsTable, OffersTable } from "../components/Tables";
import { TitrationScale } from "../components/TitrationScale";
import { Notice, Section, TextInput } from "../components/ui";
import { api, exportUrl } from "../lib/api";
import { money, when } from "../lib/format";
import type { CostBreakdown, RunState } from "../lib/types";
import { useRun } from "../lib/useRun";
import { Slider } from "./Analyze";

export default function Report() {
  const { runId = "" } = useParams();
  const { run, setRun, stageStatus, seconds, error } = useRun(runId);

  if (error)
    return (
      <div className="max-w-xl">
        <h1 className="font-cond text-[2rem] font-semibold">This analysis stopped</h1>
        <Notice tone="over">{error}</Notice>
        <p className="mt-4 text-sm">
          <Link to="/" className="text-cobalt hover:underline">
            Start a new analysis
          </Link>
        </p>
      </div>
    );

  if (!run)
    return (
      <div className="max-w-md">
        <h1 className="font-cond text-[2rem] font-semibold tracking-tight mb-1">Running the analysis</h1>
        <p className="text-slate mb-8">Each step appears as it finishes. Live vendor searches can take up to half a minute.</p>
        <StageTrack status={stageStatus} seconds={seconds} />
      </div>
    );

  if (run.status === "needs_input") return <NeedsInput run={run} />;

  return <Finished run={run} setRun={setRun} />;
}

function NeedsInput({ run }: { run: RunState }) {
  const navigate = useNavigate();
  const pick = useMutation({
    mutationFn: (i: number) => api.pickCompound(run.run_id, run.candidates[i]),
    onSuccess: ({ run_id }) => navigate(`/runs/${run_id}`),
  });
  return (
    <div className="max-w-3xl">
      <h1 className="font-cond text-[2rem] font-semibold tracking-tight">Which compound did you mean?</h1>
      {run.candidates.length ? (
        <>
          <p className="text-slate mb-6">“{run.query.raw_input}” matches more than one compound.</p>
          <ul className="grid sm:grid-cols-2 gap-3">
            {run.candidates.map((c, i) => (
              <li key={c.inchikey}>
                <button type="button" onClick={() => pick.mutate(i)} className="w-full text-left rounded-md border border-rule bg-surface p-3 hover:border-cobalt cursor-pointer">
                  <Molecule smiles={c.smiles} alt={c.label} w={260} h={160} plate={false} />
                  <div className="mt-2 font-medium">{c.label}</div>
                  <div className="text-xs text-slate">{c.formula}</div>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="space-y-2 mt-4">
          {run.warnings.map((w) => (
            <Notice key={w} tone="over">
              {w}
            </Notice>
          ))}
          <Link to="/" className="inline-block mt-4 text-sm text-cobalt hover:underline">
            Try a different name or draw the structure
          </Link>
        </div>
      )}
    </div>
  );
}

function verdictCopy(c: CostBreakdown | null) {
  if (!c || c.fits_budget == null || c.best_cost_aud == null)
    return { tone: "partial" as const, headline: "Not enough prices to decide", sub: "Some prices are missing, so the total can't be compared with the budget." };
  const how = c.cheapest === "make" ? "Making it" : "Buying it";
  const gap = Math.abs(c.gap_aud ?? 0);
  return c.fits_budget
    ? { tone: "fits" as const, headline: "Fits the budget", sub: `${how} costs ${money(c.best_cost_aud)}, ${money(gap)} under your ${money(c.budget_aud)} budget.` }
    : { tone: "over" as const, headline: "Over budget", sub: `The cheapest option, ${how.toLowerCase()}, costs ${money(c.best_cost_aud)}: ${money(gap)} more than your ${money(c.budget_aud)} budget.` };
}

function Finished({ run, setRun }: { run: RunState; setRun: (r: RunState) => void }) {
  const q = run.query;
  const c = run.cost;
  const v = verdictCopy(c);
  const best = c?.buy ?? null;

  return (
    <article>
      {/* ---------- header ---------- */}
      <header className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h1 className="font-cond text-[2.25rem] leading-tight font-semibold tracking-tight break-words">
            {run.compound?.label ?? q.raw_input}
          </h1>
          <p className="text-slate">
            {q.quantity} {q.quantity_unit}
            {q.min_purity ? ` at ${q.min_purity}% purity or better` : ""}, budget {q.budget.toLocaleString("en-AU")} {q.currency}.{" "}
            <span className="text-faint">Run on {when(run.created_at)}</span>
          </p>
        </div>
        <ExportMenu runId={run.run_id} hasMaterials={run.materials.length > 0} />
      </header>

      {/* ---------- verdict ---------- */}
      <div className="grid gap-8 md:grid-cols-[260px_minmax(0,1fr)] items-start">
        {run.compound && <Molecule smiles={run.compound.smiles} alt={`Structure of ${run.compound.label}`} w={300} h={220} className="aspect-[15/11]" />}
        <div className="min-w-0">
          <p
            className={clsx(
              "font-cond text-[2.75rem] leading-none font-semibold tracking-tight",
              v.tone === "fits" && "text-fits",
              v.tone === "over" && "text-over",
              v.tone === "partial" && "text-partial",
            )}
          >
            {v.headline}
          </p>
          <p className="mt-3 text-lg max-w-[60ch]">{v.sub}</p>
          {run.explanation && <p className="mt-3 text-slate max-w-[68ch]">{run.explanation}</p>}
          {run.uses_demo_data && (
            <p className="mt-3 text-sm text-partial">Some prices here are sample data, not live quotes.</p>
          )}
        </div>
      </div>

      {c && (
        <div className="mt-8 border-y border-rule py-5">
          <TitrationScale cost={c} />
        </div>
      )}

      {/* ---------- body ---------- */}
      <div className="mt-10 grid gap-10 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0">
          <Section title="Availability in the market" aside={run.offers.length ? `${run.offers.length} offers, sorted by price per gram` : undefined}>
            {run.offers.length ? (
              <OffersTable offers={run.offers} best={best} />
            ) : (
              <p className="text-slate">None of the vendors searched sell this compound.</p>
            )}
          </Section>

          {run.route ? (
            <>
              <Section title={run.route.source === "known" ? "Established synthesis route" : "Predicted synthesis route"}>
                <RouteSteps route={run.route} assumedYield={q.default_step_yield} />
              </Section>
              <Section title="Starting materials" aside={`Amounts for ${q.quantity} ${q.quantity_unit} of product`}>
                <MaterialsTable materials={run.materials} />
              </Section>
            </>
          ) : (
            (q.compare_synthesis || !run.offers.length) && (
              <Section title="Synthesis route">
                <p className="text-slate">No route was found for this compound.</p>
              </Section>
            )
          )}

          {run.warnings.length > 0 && (
            <Section title="Notes">
              <ul className="space-y-1.5 text-sm list-disc pl-5 marker:text-faint">
                {run.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        <Assumptions run={run} onUpdate={setRun} />
      </div>
    </article>
  );
}

function ExportMenu({ runId, hasMaterials }: { runId: string; hasMaterials: boolean }) {
  return (
    <div className="flex flex-wrap gap-2">
      <a href={exportUrl.html(runId)} className="inline-flex items-center gap-2 h-9 px-3 rounded-md border border-rule bg-surface text-sm hover:border-slate">
        <FileText className="size-4" aria-hidden /> Report
      </a>
      <a href={exportUrl.csv(runId, "offers")} className="inline-flex items-center gap-2 h-9 px-3 rounded-md border border-rule bg-surface text-sm hover:border-slate">
        <Download className="size-4" aria-hidden /> Offers CSV
      </a>
      {hasMaterials && (
        <a href={exportUrl.csv(runId, "materials")} className="inline-flex items-center gap-2 h-9 px-3 rounded-md border border-rule bg-surface text-sm hover:border-slate">
          <Download className="size-4" aria-hidden /> Materials CSV
        </a>
      )}
    </div>
  );
}

/** Editing an assumption recalculates the cost; the scale above moves to show what changed. */
function Assumptions({ run, onUpdate }: { run: RunState; onUpdate: (r: RunState) => void }) {
  const q = run.query;
  const [stepYield, setStepYield] = useState(q.default_step_yield);
  const [margin, setMargin] = useState(q.consumables_margin);
  const [quantity, setQuantity] = useState(q.quantity);
  const [budget, setBudget] = useState(q.budget);
  const first = useRef(true);

  const recost = useMutation({
    mutationFn: () => api.recost(run.run_id, { default_step_yield: stepYield, consumables_margin: margin, quantity, budget }),
    onSuccess: onUpdate,
  });

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (!(quantity > 0) || !(budget >= 0)) return;
    const t = setTimeout(() => recost.mutate(), 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepYield, margin, quantity, budget]);

  return (
    <aside className="xl:sticky xl:top-8 self-start border-t xl:border-t-0 xl:border-l border-rule pt-5 xl:pt-0 xl:pl-8">
      <h2 className="font-cond text-xl font-semibold tracking-tight">Assumptions</h2>
      <p className="text-sm text-slate mt-1 mb-5">Change these to see how the cost moves.</p>
      <div className="space-y-5">
        <label className="block">
          <span className="text-sm font-medium">Quantity ({q.quantity_unit})</span>
          <TextInput type="number" min={0.001} step="any" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} className="tnum mt-1.5" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Budget ({q.currency})</span>
          <TextInput type="number" min={0} step="any" value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="tnum mt-1.5" />
        </label>
        {run.route && (
          <>
            <Slider label="Assumed yield per step" hint="For steps without a recorded yield" value={stepYield} min={0.1} max={1} step={0.05} onChange={setStepYield} format={(x) => `${Math.round(x * 100)}%`} />
            <Slider label="Solvents and consumables" value={margin} min={0} max={1} step={0.05} onChange={setMargin} format={(x) => `+${Math.round(x * 100)}%`} />
          </>
        )}
      </div>
      <p className="text-xs mt-4 h-4 text-slate" aria-live="polite">
        {recost.isPending ? "Recalculating…" : recost.isError ? <span className="text-over">{recost.error.message}</span> : ""}
      </p>
      <div className="mt-4">
        <Link to="/" className="flex items-center justify-center h-9 rounded-md border border-rule bg-surface text-sm font-medium hover:border-slate">
          New analysis
        </Link>
      </div>
      {run.compound && (
        <details className="mt-8 group">
          <summary className="text-sm font-medium cursor-pointer list-none flex justify-between">
            Identifiers <span className="text-slate group-open:rotate-180 transition-transform">⌄</span>
          </summary>
          <div className="mt-3">
            <CompoundFacts compound={run.compound} />
          </div>
        </details>
      )}
    </aside>
  );
}
