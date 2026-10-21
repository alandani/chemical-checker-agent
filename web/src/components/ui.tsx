import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

type ButtonVariant = "primary" | "quiet" | "outline";

export function Button({
  variant = "primary",
  busy,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={props.disabled || busy}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-md px-3.5 h-9 text-sm font-medium whitespace-nowrap shrink-0 transition-colors",
        "disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer",
        variant === "primary" && "bg-cobalt text-cobalt-ink hover:brightness-110",
        variant === "outline" && "border border-rule bg-surface text-ink hover:border-slate",
        variant === "quiet" && "text-slate hover:text-ink hover:bg-cobalt-soft/60",
        className,
      )}
    >
      {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-slate">{hint}</p>}
    </div>
  );
}

const inputBase =
  "h-9 w-full rounded-md border border-rule bg-surface px-2.5 text-sm text-ink placeholder:text-faint " +
  "hover:border-slate focus:border-cobalt focus:outline-none focus:ring-2 focus:ring-cobalt/25";

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(inputBase, className)} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={clsx(inputBase, "pr-7 cursor-pointer", className)}>
      {children}
    </select>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-rule bg-paper p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "h-8 rounded px-3 text-sm transition-colors cursor-pointer",
            value === o.value ? "bg-surface text-ink font-medium shadow-[0_0_0_1px_var(--rule)]" : "text-slate hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export type Tone = "fits" | "over" | "partial" | "neutral" | "cobalt";

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tone === "fits" && "bg-fits-soft text-fits",
        tone === "over" && "bg-over-soft text-over",
        tone === "partial" && "bg-partial-soft text-partial",
        tone === "neutral" && "bg-paper text-slate border border-rule",
        tone === "cobalt" && "bg-cobalt-soft text-cobalt",
      )}
    >
      {children}
    </span>
  );
}

export function Dot({ tone }: { tone: Tone }) {
  return (
    <span
      aria-hidden
      className={clsx(
        "inline-block size-2 rounded-full",
        tone === "fits" && "bg-fits",
        tone === "over" && "bg-over",
        tone === "partial" && "bg-partial",
        tone === "neutral" && "bg-faint",
        tone === "cobalt" && "bg-cobalt",
      )}
    />
  );
}

/** A section introduced by a heading and a hairline rule, not a card. */
export function Section({
  title,
  aside,
  children,
  id,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section id={id} className="border-t border-rule pt-5 mt-10 first:mt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-4">
        <h2 className="font-cond text-xl font-semibold tracking-tight">{title}</h2>
        {aside && <div className="text-sm text-slate">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-8">
      <h1 className="font-cond text-[2rem] leading-tight font-semibold tracking-tight">{title}</h1>
      {children && <div className="mt-1 text-slate max-w-[62ch]">{children}</div>}
    </header>
  );
}

export function Notice({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div
      className={clsx(
        "rounded-md px-3 py-2 text-sm border-l-[3px]",
        tone === "over" && "border-over bg-over-soft",
        tone === "partial" && "border-partial bg-partial-soft",
        tone === "fits" && "border-fits bg-fits-soft",
        (tone === "neutral" || tone === "cobalt") && "border-cobalt bg-cobalt-soft",
      )}
    >
      {children}
    </div>
  );
}
