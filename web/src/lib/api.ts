import type { AdminOverview, Compound, Health, InputType, Offer, Query, RunState, RunSummary } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/api/health"),
  resolve: (raw_input: string, input_type: InputType = "auto") =>
    post<{ compound: Compound | null; candidates: Compound[]; error: string | null }>("/api/resolve", {
      raw_input,
      input_type,
    }),
  startRun: (query: Query, compound: Compound | null) =>
    post<{ run_id: string }>("/api/runs", { query, compound }),
  run: (id: string) => request<RunState>(`/api/runs/${id}`),
  runs: () => request<RunSummary[]>("/api/runs"),
  recost: (
    id: string,
    body: Partial<{ quantity: number; default_step_yield: number; consumables_margin: number; budget: number }>,
  ) => post<RunState>(`/api/runs/${id}/recost`, body),
  pickCompound: (id: string, compound: Compound) => post<{ run_id: string }>(`/api/runs/${id}/compound`, { compound }),
  admin: () => request<AdminOverview>("/api/admin/overview"),
  scrape: (term: string, vendors: string[]) =>
    post<{ compound: Compound; offers: Offer[]; warnings: string[] }>("/api/admin/scrape", { term, vendors }),
  reloadDemo: () => post<Record<string, number>>("/api/admin/demo", {}),
  removeDemo: () => request<Record<string, number>>("/api/admin/demo", { method: "DELETE" }),
};

export const svgUrl = {
  molecule: (smiles: string, theme: string, w = 360, h = 260) =>
    `/api/svg/molecule?${new URLSearchParams({ smiles, theme, w: String(w), h: String(h) })}`,
  reaction: (smiles: string, theme: string, w = 760, h = 220) =>
    `/api/svg/reaction?${new URLSearchParams({ smiles, theme, w: String(w), h: String(h) })}`,
};

export const exportUrl = {
  html: (id: string) => `/api/runs/${id}/export/report.html`,
  csv: (id: string, table: "offers" | "materials") => `/api/runs/${id}/export/${table}.csv`,
};
