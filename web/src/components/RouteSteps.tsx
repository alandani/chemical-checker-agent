import { percent } from "../lib/format";
import type { Route } from "../lib/types";
import { Reaction } from "./Structure";
import { Pill } from "./ui";

/** Route steps are a real sequence: numbered, in lab order. */
export function RouteSteps({ route, assumedYield }: { route: Route; assumedYield: number }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-4 text-sm text-slate">
        {route.source === "known" ? <Pill tone="fits">Known route</Pill> : <Pill tone="partial">AI-predicted route</Pill>}
        <span>
          {route.steps.length} {route.steps.length === 1 ? "step" : "steps"}
          {route.reference ? `, from ${route.reference}` : ""}
        </span>
      </div>
      {route.notes && <p className="text-sm text-slate mb-4 max-w-[70ch]">{route.notes}</p>}
      <ol className="space-y-6">
        {route.steps.map((step, i) => (
          <li key={i} className="grid grid-cols-[2.25rem_1fr] gap-x-3">
            <span className="font-cond text-2xl font-semibold text-cobalt tnum leading-none pt-1">{i + 1}</span>
            <div className="min-w-0">
              <div className="plate border border-rule rounded-md px-2 py-1">
                <Reaction smiles={step.reaction_smiles} alt={`Step ${i + 1} reaction`} />
              </div>
              <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                <div className="flex gap-1.5">
                  <dt className="text-slate">Yield</dt>
                  <dd className="tnum font-medium">
                    {step.yield != null ? percent(step.yield) : <>{percent(assumedYield)} <span className="text-slate font-normal">(assumed)</span></>}
                  </dd>
                </div>
                {step.conditions && (
                  <div className="flex gap-1.5 min-w-0">
                    <dt className="text-slate">Conditions</dt>
                    <dd>{step.conditions}</dd>
                  </div>
                )}
              </dl>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
