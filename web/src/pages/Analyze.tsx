import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronDown, Search } from "lucide-react";
import { lazy, Suspense, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { CompoundFacts } from "../components/CompoundFacts";
import { Molecule } from "../components/Structure";
import { Button, Field, Notice, PageHeader, Segmented, Select, TextInput } from "../components/ui";
import { api } from "../lib/api";
import type { Compound, InputType, MassUnit, Query } from "../lib/types";

const StructureEditor = lazy(() => import("../components/StructureEditor"));

type Method = "name" | "smiles" | "draw";

const EXAMPLES: { label: string; value: string; method: Method }[] = [
  { label: "Topiramate", value: "Topiramate", method: "name" },
  { label: "97240-79-4", value: "97240-79-4", method: "name" },
  { label: "N-benzylbenzamide", value: "O=C(NCc1ccccc1)c1ccccc1", method: "smiles" },
];

export default function Analyze() {
  const navigate = useNavigate();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });

  const [method, setMethod] = useState<Method>("name");
  const [text, setText] = useState("");
  const [lookedUp, setLookedUp] = useState("");
  const [compound, setCompound] = useState<Compound | null>(null);
  const [candidates, setCandidates] = useState<Compound[]>([]);

  const [quantity, setQuantity] = useState(1);
  const [unit, setUnit] = useState<MassUnit>("g");
  const [purity, setPurity] = useState(95);
  const [budget, setBudget] = useState(500);
  const [currency, setCurrency] = useState("AUD");
  const [showMore, setShowMore] = useState(false);
  const [compare, setCompare] = useState(false);
  const [allowPredicted, setAllowPredicted] = useState(true);
  const [regions, setRegions] = useState<string[]>([]);
  const [maxSteps, setMaxSteps] = useState(5);
  const [margin, setMargin] = useState(0.15);
  const [stepYield, setStepYield] = useState(0.7);

  const lookup = useMutation({
    mutationFn: ({ raw, type }: { raw: string; type: InputType }) => api.resolve(raw, type),
    onMutate: () => {
      setCompound(null);
      setCandidates([]);
    },
    onSuccess: (res, vars) => {
      setLookedUp(vars.raw);
      if (res.compound) setCompound(res.compound);
      else setCandidates(res.candidates);
    },
  });

  const start = useMutation({
    mutationFn: (q: Query) => api.startRun(q, compound),
    onSuccess: ({ run_id }) => navigate(`/runs/${run_id}`),
  });

  function doLookup(raw: string, m: Method = method) {
    if (!raw.trim()) return;
    lookup.mutate({ raw: raw.trim(), type: m === "name" ? "auto" : "smiles" });
  }

  function submitLookup(e: FormEvent) {
    e.preventDefault();
    doLookup(text);
  }

  function run(e: FormEvent) {
    e.preventDefault();
    if (!compound) return;
    start.mutate({
      raw_input: lookedUp || compound.label,
      input_type: method === "name" ? "auto" : "smiles",
      quantity,
      quantity_unit: unit,
      min_purity: purity || null,
      budget,
      currency,
      regions: regions.length ? regions : null,
      allow_predicted: allowPredicted,
      compare_synthesis: compare,
      max_steps: maxSteps,
      consumables_margin: margin,
      default_step_yield: stepYield,
    });
  }

  const resolveError = lookup.data?.error ?? (lookup.error instanceof Error ? lookup.error.message : null);

  return (
    <div>
      <PageHeader title="New analysis">
        Find out whether a compound fits your budget, and whether it's cheaper to buy it or make it.
      </PageHeader>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* ---------- compound ---------- */}
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <h2 className="font-cond text-xl font-semibold tracking-tight">Compound</h2>
            <Segmented<Method>
              label="How to enter the compound"
              value={method}
              onChange={(m) => {
                setMethod(m);
                setText("");
              }}
              options={[
                { value: "name", label: "Name or CAS" },
                { value: "smiles", label: "SMILES" },
                { value: "draw", label: "Draw" },
              ]}
            />
          </div>

          {method !== "draw" ? (
            <form onSubmit={submitLookup} className="flex gap-2">
              <label htmlFor="compound-input" className="sr-only">
                {method === "name" ? "Compound name or CAS number" : "SMILES string"}
              </label>
              <TextInput
                id="compound-input"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={method === "name" ? "Topiramate, or a CAS number like 97240-79-4" : "O=C(NCc1ccccc1)c1ccccc1"}
                className={method === "smiles" ? "font-mono" : ""}
                autoComplete="off"
                spellCheck={false}
              />
              <Button type="submit" busy={lookup.isPending} disabled={!text.trim()}>
                <Search className="size-4" aria-hidden />
                Look up
              </Button>
            </form>
          ) : (
            <Suspense fallback={<div className="h-[440px] plate border border-rule rounded-md grid place-items-center text-sm text-slate">Loading the structure editor…</div>}>
              <StructureEditor onUse={(smiles) => doLookup(smiles, "draw")} />
            </Suspense>
          )}

          <div className="mt-5" aria-live="polite">
            {resolveError && <Notice tone="over">{resolveError}</Notice>}

            {candidates.length > 0 && (
              <div>
                <p className="text-sm mb-3">
                  “{lookedUp}” matches more than one compound. Choose the one you mean.
                </p>
                <ul className="grid sm:grid-cols-2 gap-3">
                  {candidates.map((c) => (
                    <li key={c.inchikey}>
                      <button
                        type="button"
                        onClick={() => {
                          setCompound(c);
                          setCandidates([]);
                        }}
                        className="w-full text-left rounded-md border border-rule bg-surface p-3 hover:border-cobalt cursor-pointer"
                      >
                        <Molecule smiles={c.smiles} alt={c.label} w={240} h={150} plate={false} />
                        <div className="mt-2 text-sm font-medium">{c.label}</div>
                        <div className="text-xs text-slate tnum">
                          {c.formula}
                          {c.cas ? `, CAS ${c.cas}` : ""}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {compound ? (
              <div className="grid gap-6 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-start">
                <Molecule smiles={compound.smiles} alt={`Structure of ${compound.label}`} w={420} h={300} className="aspect-[7/5]" />
                <div>
                  <h3 className="font-cond text-3xl font-semibold tracking-tight leading-tight break-words">{compound.label}</h3>
                  <p className="text-sm text-slate mt-1 mb-4">Check this is the compound you mean before running.</p>
                  <CompoundFacts compound={compound} />
                  <code className="mt-4 block text-xs text-slate font-mono break-all">{compound.smiles}</code>
                </div>
              </div>
            ) : (
              !candidates.length &&
              !resolveError && (
                <div className="plate border border-dashed border-rule rounded-md h-[260px] grid place-items-center text-center px-6">
                  <div>
                    <p className="text-slate text-sm">The structure appears here once the compound is found.</p>
                    <p className="text-sm mt-3 flex flex-wrap justify-center gap-2 items-center">
                      <span className="text-slate">Try</span>
                      {EXAMPLES.map((ex) => (
                        <button
                          key={ex.label}
                          type="button"
                          onClick={() => {
                            setMethod(ex.method);
                            setText(ex.value);
                            doLookup(ex.value, ex.method);
                          }}
                          className="rounded-full border border-rule bg-surface px-2.5 py-0.5 text-cobalt hover:border-cobalt cursor-pointer"
                        >
                          {ex.label}
                        </button>
                      ))}
                    </p>
                  </div>
                </div>
              )
            )}
          </div>
        </div>

        {/* ---------- requirements ---------- */}
        <form onSubmit={run} className="lg:border-l lg:border-rule lg:pl-10 space-y-5" aria-label="Requirements">
          <h2 className="font-cond text-xl font-semibold tracking-tight">Requirements</h2>

          <Field label="Quantity needed" htmlFor="qty">
            <div className="flex gap-2">
              <TextInput id="qty" type="number" min={0.001} step="any" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} className="tnum" required />
              <Select aria-label="Unit" value={unit} onChange={(e) => setUnit(e.target.value as MassUnit)} className="w-20">
                <option value="mg">mg</option>
                <option value="g">g</option>
                <option value="kg">kg</option>
              </Select>
            </div>
          </Field>

          <Field label="Minimum purity" htmlFor="purity" hint="Offers below this purity aren't used. Leave at 0 for any.">
            <div className="relative">
              <TextInput id="purity" type="number" min={0} max={100} step={0.5} value={purity} onChange={(e) => setPurity(Number(e.target.value))} className="tnum pr-8" />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-slate">%</span>
            </div>
          </Field>

          <Field label="Budget" htmlFor="budget">
            <div className="flex gap-2">
              <TextInput id="budget" type="number" min={0} step="any" value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="tnum" required />
              <Select aria-label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)} className="w-24">
                {["AUD", "USD", "EUR", "GBP", "JPY", "CNY"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </div>
          </Field>

          <label className="flex items-start gap-2.5 text-sm cursor-pointer">
            <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="mt-1 accent-[var(--cobalt)]" />
            <span>
              Also cost a synthesis route
              <span className="block text-xs text-slate">Even when the compound can be bought</span>
            </span>
          </label>

          <div className="border-t border-rule pt-4">
            <button
              type="button"
              onClick={() => setShowMore((s) => !s)}
              aria-expanded={showMore}
              className="flex w-full items-center justify-between text-sm font-medium cursor-pointer"
            >
              More options
              <ChevronDown className={`size-4 text-slate transition-transform ${showMore ? "rotate-180" : ""}`} aria-hidden />
            </button>
            {showMore && (
              <div className="mt-4 space-y-5">
                <label className="flex items-center gap-2.5 text-sm cursor-pointer">
                  <input type="checkbox" checked={allowPredicted} onChange={(e) => setAllowPredicted(e.target.checked)} className="accent-[var(--cobalt)]" />
                  Allow AI-predicted routes
                </label>
                {health.data && (
                  <fieldset>
                    <legend className="text-sm font-medium mb-2">Vendor regions</legend>
                    <div className="flex flex-wrap gap-1.5">
                      {health.data.regions.map((r) => {
                        const on = regions.includes(r);
                        return (
                          <button
                            key={r}
                            type="button"
                            aria-pressed={on}
                            onClick={() => setRegions((rs) => (on ? rs.filter((x) => x !== r) : [...rs, r]))}
                            className={`rounded-full border px-2.5 py-0.5 text-xs cursor-pointer ${on ? "border-cobalt bg-cobalt-soft text-cobalt" : "border-rule text-slate hover:text-ink"}`}
                          >
                            {r}
                          </button>
                        );
                      })}
                    </div>
                    <p className="text-xs text-slate mt-1.5">{regions.length ? "Only these regions are searched." : "All regions are searched."}</p>
                  </fieldset>
                )}
                <Slider label="Most synthesis steps" value={maxSteps} min={1} max={8} step={1} onChange={setMaxSteps} format={(v) => String(v)} />
                <Slider label="Assumed yield per step" hint="Used when a step has no recorded yield" value={stepYield} min={0.1} max={1} step={0.05} onChange={setStepYield} format={(v) => `${Math.round(v * 100)}%`} />
                <Slider label="Solvents and consumables" hint="Added on top of starting-material cost" value={margin} min={0} max={1} step={0.05} onChange={setMargin} format={(v) => `+${Math.round(v * 100)}%`} />
              </div>
            )}
          </div>

          {start.error && <Notice tone="over">{start.error.message}</Notice>}
          <Button type="submit" className="w-full h-11 text-[15px]" disabled={!compound} busy={start.isPending}>
            Run analysis
          </Button>
          {!compound && <p className="text-xs text-slate -mt-2">Look up the compound first.</p>}
        </form>
      </div>
    </div>
  );
}

export function Slider({
  label,
  hint,
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format: (v: number) => string;
}) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="tnum text-ink">{format(value)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full mt-1.5" />
      {hint && <span className="block text-xs text-slate">{hint}</span>}
    </label>
  );
}
