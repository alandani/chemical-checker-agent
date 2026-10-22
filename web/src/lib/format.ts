const aud = new Intl.NumberFormat("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const audRound = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 0 });

// Always "A$" so prices never read as US dollars.
const sign = (n: number) => (n < 0 ? "−" : "");
export const money = (n: number | null | undefined) => (n == null ? "—" : `${sign(n)}A$${aud.format(Math.abs(n))}`);
export const moneyRound = (n: number | null | undefined) => (n == null ? "—" : `${sign(n)}A$${audRound.format(Math.abs(n))}`);

export function grams(g: number): string {
  if (g >= 1000) return `${(g / 1000).toLocaleString("en-AU", { maximumFractionDigits: 2 })} kg`;
  if (g < 1) return `${(g * 1000).toLocaleString("en-AU", { maximumFractionDigits: 1 })} mg`;
  return `${g.toLocaleString("en-AU", { maximumFractionDigits: 2 })} g`;
}

export const pack = (qty: number | null, unit: string | null) => (qty && unit ? `${qty} ${unit}` : "—");

export const percent = (x: number | null | undefined, digits = 0) =>
  x == null ? "—" : `${(x * 100).toFixed(digits)}%`;

export function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString("en-AU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
