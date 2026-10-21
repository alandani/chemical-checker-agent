// Mirrors core/models.py (API responses use field aliases, e.g. `yield`).

export type MassUnit = "mg" | "g" | "kg";
export type InputType = "auto" | "smiles" | "name" | "cas";

export interface Query {
  raw_input: string;
  input_type: InputType;
  quantity: number;
  quantity_unit: MassUnit;
  min_purity: number | null;
  budget: number;
  currency: string;
  regions: string[] | null;
  allow_predicted: boolean;
  compare_synthesis: boolean;
  max_steps: number;
  consumables_margin: number;
  default_step_yield: number;
}

export interface Compound {
  inchikey: string;
  smiles: string;
  name: string | null;
  cas: string | null;
  formula: string | null;
  mol_weight: number | null;
  pubchem_cid: number | null;
  label: string;
}

export interface Offer {
  vendor: string;
  compound_inchikey: string;
  pack_qty: number | null;
  pack_unit: string | null;
  price: number | null;
  currency: string | null;
  price_aud: number | null;
  price_aud_per_g: number | null;
  pack_grams: number | null;
  purity: number | null;
  url: string | null;
  in_stock: boolean | null;
  quote_only: boolean;
  is_demo: boolean;
  scraped_at: string;
}

export interface Purchase {
  offer: Offer;
  n_packs: number;
  total_aud: number;
}

export interface RouteStep {
  reactants: string[];
  product: string;
  equivalents: number[] | null;
  conditions: string | null;
  yield: number | null;
  reference: string | null;
  reaction_smiles: string;
}

export interface Route {
  source: "known" | "predicted";
  steps: RouteStep[];
  score: number | null;
  reference: string | null;
  notes: string | null;
}

export interface MaterialCost {
  smiles: string;
  inchikey: string | null;
  name: string | null;
  grams_needed: number;
  purchase: Purchase | null;
  is_demo: boolean;
  priced: boolean;
  line_cost_aud: number | null;
}

export interface CostBreakdown {
  budget_aud: number;
  buy: Purchase | null;
  make_materials_aud: number | null;
  make_total_aud: number | null;
  make_complete: boolean;
  cheapest: "buy" | "make" | null;
  best_cost_aud: number | null;
  fits_budget: boolean | null;
  gap_aud: number | null;
}

export type StageName =
  | "RESOLVE"
  | "CHECK_MARKET"
  | "FIND_KNOWN_ROUTE"
  | "PREDICT_ROUTE"
  | "PRICE_MATERIALS"
  | "COST"
  | "EXPLAIN"
  | "DONE"
  | "NEEDS_INPUT";

export interface RunState {
  run_id: string;
  created_at: string;
  status: "running" | "needs_input" | "done";
  current: StageName;
  query: Query;
  compound: Compound | null;
  candidates: Compound[];
  offers: Offer[];
  route: Route | null;
  alternative_routes: Route[];
  materials: MaterialCost[];
  cost: CostBreakdown | null;
  explanation: string | null;
  warnings: string[];
  timings: Record<string, number>;
  uses_demo_data: boolean;
}

export interface StageEvent {
  kind: "started" | "finished";
  stage: StageName;
  label: string;
  seconds: number | null;
}

export interface Health {
  ok: boolean;
  llm_enabled: boolean;
  live_scraping: boolean;
  route_prediction: boolean;
  base_currency: string;
  regions: string[];
}

export interface RunSummary {
  run_id: string;
  created_at: string | null;
  compound: string | null;
  status: string;
  fits_budget: boolean | null;
  best_cost_aud: number | null;
  budget_aud: number | null;
}

export interface VendorRow {
  key: string;
  name: string;
  region: string;
  base_url: string;
  enabled: boolean;
  verified: boolean;
  requires_js: boolean;
  notes: string;
  last_scrape_at: string | null;
  last_scrape_ok: boolean | null;
  success_rate: number | null;
  offers: number;
  last_error: string | null;
}

export interface AdminOverview {
  stats: { compounds_priced: number; offers: number; reactions: number };
  vendors: VendorRow[];
  rates: { currency: string; rate: number; fallback: boolean }[];
  route_prediction_ready: boolean;
}
