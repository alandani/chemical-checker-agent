import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { DataTable, OffersTable } from "../components/Tables";
import { Button, Dot, Notice, PageHeader, Pill, Section, TextInput } from "../components/ui";
import { api } from "../lib/api";
import { when } from "../lib/format";

export default function DataAdmin() {
  const qc = useQueryClient();
  const overview = useQuery({ queryKey: ["admin"], queryFn: api.admin });
  const [term, setTerm] = useState("");
  const [picked, setPicked] = useState<string[] | null>(null);

  const vendors = overview.data?.vendors ?? [];
  const selected = picked ?? vendors.filter((v) => v.enabled).map((v) => v.key);

  const scrape = useMutation({
    mutationFn: () => api.scrape(term.trim(), selected),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
  const demo = useMutation({
    mutationFn: api.reloadDemo,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (term.trim() && selected.length) scrape.mutate();
  }

  const s = overview.data?.stats;

  return (
    <div>
      <PageHeader title="Data">Where prices and routes come from, and how healthy each vendor source is.</PageHeader>

      {s && (
        <dl className="flex flex-wrap gap-x-12 gap-y-4 border-y border-rule py-4 mb-2">
          {[
            ["Compounds with prices", s.compounds_priced],
            ["Offers stored", s.offers],
            ["Known reactions", s.reactions],
          ].map(([k, v]) => (
            <div key={k as string}>
              <dt className="text-sm text-slate">{k}</dt>
              <dd className="font-cond text-3xl font-semibold tnum">{(v as number).toLocaleString("en-AU")}</dd>
            </div>
          ))}
        </dl>
      )}

      <Section title="Vendors" aside="Turn vendors on with ENABLED_VENDORS in .env, after checking their search URL">
        {overview.isLoading && <p className="text-slate">Loading…</p>}
        <DataTable caption="Vendors" head={["Vendor", "Region", "Search", "Search URL checked", "Last search", <span className="block text-right">Offers</span>]}>
          {vendors.map((v) => (
            <tr key={v.key}>
              <td className="py-2.5 pr-4">
                <a href={v.base_url} target="_blank" rel="noreferrer" className="font-medium hover:text-cobalt">
                  {v.name}
                </a>
                {v.requires_js && <div className="text-xs text-slate">Needs a headless browser</div>}
              </td>
              <td className="py-2.5 pr-4 text-slate">{v.region}</td>
              <td className="py-2.5 pr-4">{v.enabled ? <Pill tone="cobalt">On</Pill> : <Pill>Off</Pill>}</td>
              <td className="py-2.5 pr-4">{v.verified ? <span className="text-fits">Yes</span> : <span className="text-partial">Not yet</span>}</td>
              <td className="py-2.5 pr-4">
                {v.last_scrape_at ? (
                  <span className="inline-flex items-center gap-2" title={v.last_error ?? undefined}>
                    <Dot tone={v.last_scrape_ok ? "fits" : "over"} />
                    {when(v.last_scrape_at)}
                    {v.success_rate != null && <span className="text-slate">({Math.round(v.success_rate * 100)}% ok)</span>}
                  </span>
                ) : (
                  <span className="text-faint">Never</span>
                )}
              </td>
              <td className="py-2.5 text-right tnum">{v.offers}</td>
            </tr>
          ))}
        </DataTable>
      </Section>

      <Section title="Search vendors now">
        <form onSubmit={submit} className="space-y-4 max-w-3xl">
          <div className="flex gap-2">
            <label htmlFor="scrape-term" className="sr-only">
              Compound name, CAS or SMILES
            </label>
            <TextInput id="scrape-term" value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Name, CAS number or SMILES" />
            <Button type="submit" busy={scrape.isPending} disabled={!term.trim() || !selected.length}>
              Search
            </Button>
          </div>
          <fieldset>
            <legend className="text-sm font-medium mb-2">Vendors to search</legend>
            <div className="flex flex-wrap gap-1.5">
              {vendors.map((v) => {
                const on = selected.includes(v.key);
                return (
                  <button
                    key={v.key}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setPicked(on ? selected.filter((k) => k !== v.key) : [...selected, v.key])}
                    className={`rounded-full border px-2.5 py-0.5 text-xs cursor-pointer ${on ? "border-cobalt bg-cobalt-soft text-cobalt" : "border-rule text-slate hover:text-ink"}`}
                  >
                    {v.name}
                  </button>
                );
              })}
            </div>
          </fieldset>
        </form>
        <div className="mt-6 space-y-3" aria-live="polite">
          {scrape.error && <Notice tone="over">{scrape.error.message}</Notice>}
          {scrape.data && (
            <>
              <p className="text-sm">
                {scrape.data.offers.length} offers found for <strong>{scrape.data.compound.label}</strong>.
              </p>
              {scrape.data.warnings.map((w) => (
                <Notice key={w} tone="partial">
                  {w}
                </Notice>
              ))}
              {scrape.data.offers.length > 0 && <OffersTable offers={scrape.data.offers} best={null} />}
            </>
          )}
        </div>
      </Section>

      <Section title="Sample data">
        <p className="text-sm text-slate max-w-[65ch] mb-3">
          Fictional vendors with illustrative prices, for demos without a network connection. They're labelled “Sample” wherever they appear.
        </p>
        <Button variant="outline" onClick={() => demo.mutate()} busy={demo.isPending}>
          Reload sample data
        </Button>
        {demo.isSuccess && <p className="text-sm text-fits mt-2">Sample data reloaded.</p>}
      </Section>

      {overview.data && overview.data.rates.length > 0 && (
        <Section title="Exchange rates" aside="To AUD, refreshed every 6 hours">
          <ul className="text-sm space-y-1 tnum">
            {overview.data.rates.map((r) => (
              <li key={r.currency}>
                1 {r.currency} = {r.rate.toFixed(4)} AUD {r.fallback && <span className="text-partial">(approximate, live rate unavailable)</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
