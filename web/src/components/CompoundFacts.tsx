import type { Compound } from "../lib/types";

/** Identifier list. Mono only where the value is literally code-like data. */
export function CompoundFacts({ compound }: { compound: Compound }) {
  const rows: [string, string | null, boolean][] = [
    ["CAS", compound.cas, true],
    ["Formula", compound.formula, false],
    ["Molar mass", compound.mol_weight ? `${compound.mol_weight.toFixed(2)} g/mol` : null, false],
    ["InChIKey", compound.inchikey, true],
    ["PubChem CID", compound.pubchem_cid ? String(compound.pubchem_cid) : null, true],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-1.5 text-sm">
      {rows.map(([k, v, mono]) => (
        <div key={k} className="contents">
          <dt className="text-slate">{k}</dt>
          <dd className={mono ? "font-mono text-[13px] break-all" : "tnum"}>{v ?? <span className="text-faint">Not found</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
