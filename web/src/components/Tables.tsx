import clsx from "clsx";
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import { grams, money, pack } from "../lib/format";
import type { MaterialCost, Offer, Purchase } from "../lib/types";
import { Pill } from "./ui";

export function DataTable({ head, children, caption }: { head: ReactNode[]; children: ReactNode; caption?: string }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <table className="w-full text-sm border-collapse">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-ink/70 text-left">
            {head.map((h, i) => (
              <th key={i} scope="col" className="py-2 pr-4 font-medium text-slate whitespace-nowrap last:pr-0">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-rule">{children}</tbody>
      </table>
    </div>
  );
}

const Num = ({ children, strong }: { children: ReactNode; strong?: boolean }) => (
  <td className={clsx("py-2.5 pr-4 text-right tnum whitespace-nowrap", strong && "font-semibold")}>{children}</td>
);

function VendorLink({ url }: { url: string | null }) {
  if (!url) return <span className="text-faint">—</span>;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-cobalt hover:underline">
      Open <ExternalLink className="size-3.5" aria-hidden />
      <span className="sr-only">(opens vendor page)</span>
    </a>
  );
}

export function OffersTable({ offers, best }: { offers: Offer[]; best: Purchase | null }) {
  const sorted = [...offers].sort(
    (a, b) => (a.price_aud_per_g ?? Infinity) - (b.price_aud_per_g ?? Infinity),
  );
  const isBest = (o: Offer) =>
    best && best.offer.vendor === o.vendor && best.offer.pack_qty === o.pack_qty && best.offer.price === o.price;
  return (
    <DataTable
      caption="Vendor offers"
      head={["Vendor", "Pack", "Listed price", <span className="block text-right">A$ / pack</span>, <span className="block text-right">A$ / g</span>, <span className="block text-right">Purity</span>, "Stock", ""]}
    >
      {sorted.map((o, i) => (
        <tr key={i} className={clsx(isBest(o) && "bg-fits-soft/60")}>
          <td className="py-2.5 pr-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium">{o.vendor}</span>
              {o.is_demo && <Pill>Sample</Pill>}
              {isBest(o) && <Pill tone="fits">Best for your quantity</Pill>}
            </div>
          </td>
          <td className="py-2.5 pr-4 tnum whitespace-nowrap">{pack(o.pack_qty, o.pack_unit)}</td>
          <td className="py-2.5 pr-4 tnum whitespace-nowrap">
            {o.quote_only ? <span className="text-slate">Request a quote</span> : o.price != null ? `${o.price.toLocaleString("en-AU")} ${o.currency ?? ""}` : "—"}
          </td>
          <Num>{o.price_aud != null ? money(o.price_aud) : "—"}</Num>
          <Num strong={!!isBest(o)}>{o.price_aud_per_g != null ? money(o.price_aud_per_g) : "—"}</Num>
          <Num>{o.purity != null ? `${o.purity}%` : "—"}</Num>
          <td className="py-2.5 pr-4 text-slate">{o.in_stock == null ? "—" : o.in_stock ? "In stock" : "Out of stock"}</td>
          <td className="py-2.5">
            <VendorLink url={o.url} />
          </td>
        </tr>
      ))}
    </DataTable>
  );
}

export function MaterialsTable({ materials }: { materials: MaterialCost[] }) {
  const total = materials.reduce((s, m) => s + (m.line_cost_aud ?? 0), 0);
  return (
    <DataTable
      caption="Starting materials"
      head={["Material", <span className="block text-right">Needed</span>, "Cheapest source", "Buy", <span className="block text-right">A$ / g</span>, <span className="block text-right">Line cost</span>, ""]}
    >
      {materials.map((m, i) => {
        const p = m.purchase;
        return (
          <tr key={i}>
            <td className="py-2.5 pr-4 font-medium">{m.name ?? <code className="font-mono text-xs">{m.smiles}</code>}</td>
            <Num>{grams(m.grams_needed)}</Num>
            <td className="py-2.5 pr-4">
              {p ? (
                <span className="flex items-center gap-2 flex-wrap">
                  {p.offer.vendor}
                  {p.offer.is_demo && <Pill>Sample</Pill>}
                </span>
              ) : (
                <Pill tone="partial">No price found</Pill>
              )}
            </td>
            <td className="py-2.5 pr-4 tnum whitespace-nowrap">{p ? `${p.n_packs} × ${pack(p.offer.pack_qty, p.offer.pack_unit)}` : "—"}</td>
            <Num>{p?.offer.price_aud_per_g != null ? money(p.offer.price_aud_per_g) : "—"}</Num>
            <Num strong>{p ? money(p.total_aud) : "—"}</Num>
            <td className="py-2.5">
              <VendorLink url={p?.offer.url ?? null} />
            </td>
          </tr>
        );
      })}
      <tr className="!border-b-0">
        <td className="pt-3 pr-4 text-slate" colSpan={5}>
          Materials subtotal, before the solvents and consumables margin
        </td>
        <td className="pt-3 pr-4 text-right tnum font-semibold">{money(total)}</td>
        <td />
      </tr>
    </DataTable>
  );
}
