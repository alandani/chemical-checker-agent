// Ketcher structure editor. Large bundle, so the Analyze page lazy-loads this module.
import "ketcher-react/dist/index.css";
import { Editor } from "ketcher-react";
import { StandaloneStructServiceProvider } from "ketcher-standalone";
import type { Ketcher } from "ketcher-core";
import { useRef, useState } from "react";
import { Button } from "./ui";

const structServiceProvider = new StandaloneStructServiceProvider();

declare global {
  interface Window {
    ketcher?: Ketcher; // exposed for automated browser tests
  }
}

export default function StructureEditor({ onUse }: { onUse: (smiles: string) => void }) {
  const ketcherRef = useRef<Ketcher | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function useStructure() {
    if (!ketcherRef.current) return;
    setBusy(true);
    setError(null);
    try {
      const smiles = (await ketcherRef.current.getSmiles()).trim();
      if (!smiles) setError("Draw a structure first.");
      else onUse(smiles);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't read the drawing.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="h-[440px] rounded-md overflow-hidden border border-rule bg-white">
        <Editor
          staticResourcesUrl=""
          structServiceProvider={structServiceProvider}
          errorHandler={(message: string) => setError(message)}
          onInit={(k: Ketcher) => {
            ketcherRef.current = k;
            window.ketcher = k;
          }}
          disableMacromoleculesEditor
        />
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Button type="button" onClick={useStructure} busy={busy}>
          Look up this structure
        </Button>
        {error && <p className="text-sm text-over">{error}</p>}
      </div>
    </div>
  );
}
