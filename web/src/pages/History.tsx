import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { DataTable } from "../components/Tables";
import { Dot, PageHeader, Pill, TextInput } from "../components/ui";
import { api } from "../lib/api";
import { money, when } from "../lib/format";

export default function History() {
  const navigate = useNavigate();
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.runs });
  const [filter, setFilter] = useState("");

  const rows = useMemo(
    () => (runs.data ?? []).filter((r) => (r.compound ?? "").toLowerCase().includes(filter.trim().toLowerCase())),
    [runs.data, filter],
  );

  return (
    <div>
      <PageHeader title="History">Every analysis is saved. Open one to see its report or change its assumptions.</PageHeader>

      {runs.isLoading && <p className="text-slate">Loading…</p>}
      {runs.error && <p className="text-over">Couldn't load history: {runs.error.message}</p>}

      {runs.data && runs.data.length === 0 && (
        <div className="plate border border-dashed border-rule rounded-md p-10 text-center">
          <p className="text-slate">No analyses yet.</p>
          <Link to="/" className="inline-block mt-3 text-cobalt hover:underline">
            Run your first analysis
          </Link>
        </div>
      )}

      {runs.data && runs.data.length > 0 && (
        <>
          <div className="mb-4 max-w-xs">
            <label htmlFor="filter" className="sr-only">
              Filter by compound
            </label>
            <TextInput id="filter" placeholder="Filter by compound" value={filter} onChange={(e) => setFilter(e.target.value)} />
          </div>
          <DataTable
            caption="Past analyses"
            head={["Compound", "When", "Verdict", <span className="block text-right">Best cost</span>, <span className="block text-right">Budget</span>]}
          >
            {rows.map((r) => (
              <tr
                key={r.run_id}
                className="hover:bg-cobalt-soft/40 cursor-pointer"
                onClick={() => navigate(`/runs/${r.run_id}`)}
              >
                <td className="py-2.5 pr-4">
                  <Link to={`/runs/${r.run_id}`} className="font-medium hover:text-cobalt" onClick={(e) => e.stopPropagation()}>
                    {r.compound ?? "Unknown"}
                  </Link>
                </td>
                <td className="py-2.5 pr-4 text-slate whitespace-nowrap">{when(r.created_at)}</td>
                <td className="py-2.5 pr-4">
                  {r.status !== "done" ? (
                    <Pill>{r.status === "needs_input" ? "Needs a choice" : "Running"}</Pill>
                  ) : r.fits_budget == null ? (
                    <span className="inline-flex items-center gap-2 text-partial"><Dot tone="partial" /> Incomplete</span>
                  ) : r.fits_budget ? (
                    <span className="inline-flex items-center gap-2 text-fits"><Dot tone="fits" /> Fits</span>
                  ) : (
                    <span className="inline-flex items-center gap-2 text-over"><Dot tone="over" /> Over budget</span>
                  )}
                </td>
                <td className="py-2.5 pr-4 text-right tnum">{money(r.best_cost_aud)}</td>
                <td className="py-2.5 text-right tnum">{money(r.budget_aud)}</td>
              </tr>
            ))}
          </DataTable>
          {rows.length === 0 && <p className="text-slate mt-4">No analyses match “{filter}”.</p>}
        </>
      )}
    </div>
  );
}
