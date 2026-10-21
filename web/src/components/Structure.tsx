import clsx from "clsx";
import { useState } from "react";
import { svgUrl } from "../lib/api";
import { useTheme } from "../lib/theme";

/** RDKit-rendered structure on the graph-paper plate. */
export function Molecule({
  smiles,
  alt,
  w = 360,
  h = 260,
  className,
  plate = true,
}: {
  smiles: string;
  alt: string;
  w?: number;
  h?: number;
  className?: string;
  plate?: boolean;
}) {
  const { theme } = useTheme();
  const [failed, setFailed] = useState(false);
  return (
    <div className={clsx("rounded-md flex items-center justify-center overflow-hidden", plate && "plate border border-rule", className)}>
      {failed ? (
        <code className="p-4 text-xs text-slate break-all font-mono">{smiles}</code>
      ) : (
        <img
          src={svgUrl.molecule(smiles, theme, w, h)}
          alt={alt}
          width={w}
          height={h}
          className="max-w-full h-auto"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}

export function Reaction({ smiles, alt }: { smiles: string; alt: string }) {
  const { theme } = useTheme();
  const [failed, setFailed] = useState(false);
  if (failed) return <code className="block text-xs text-slate break-all font-mono">{smiles}</code>;
  return (
    <img
      src={svgUrl.reaction(smiles, theme)}
      alt={alt}
      width={760}
      height={220}
      className="w-full h-auto"
      onError={() => setFailed(true)}
    />
  );
}
