import { useEffect, useState } from "react";
import type { RunState, StageEvent, StageName } from "./types";
import type { StageStatus } from "../components/StageTrack";
import { STAGES } from "../components/StageTrack";

interface RunStream {
  run: RunState | null;
  setRun: (r: RunState) => void;
  stageStatus: Partial<Record<StageName, StageStatus>>;
  seconds: Partial<Record<StageName, number>>;
  error: string | null;
  finished: boolean;
}

/** Follow a run over Server-Sent Events until it finishes, then hold its final state. */
export function useRun(runId: string): RunStream {
  const [run, setRun] = useState<RunState | null>(null);
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRun(null);
    setEvents([]);
    setError(null);
    const source = new EventSource(`/api/runs/${runId}/events`);
    source.addEventListener("stage", (e) => setEvents((ev) => [...ev, JSON.parse((e as MessageEvent).data)]));
    source.addEventListener("done", (e) => {
      setRun(JSON.parse((e as MessageEvent).data));
      source.close();
    });
    source.addEventListener("failed", (e) => {
      setError(JSON.parse((e as MessageEvent).data).error);
      source.close();
    });
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) setError("Lost the connection to the server. Refresh to try again.");
    };
    return () => source.close();
  }, [runId]);

  const stageStatus: Partial<Record<StageName, StageStatus>> = {};
  const seconds: Partial<Record<StageName, number>> = {};
  for (const e of events) {
    stageStatus[e.stage] = e.kind === "started" ? "active" : "done";
    if (e.seconds != null) seconds[e.stage] = e.seconds;
  }
  if (run) {
    for (const s of STAGES) {
      if (run.timings[s.name] != null) {
        stageStatus[s.name] = "done";
        seconds[s.name] = run.timings[s.name];
      } else if (run.status === "done") stageStatus[s.name] = "skipped";
    }
  }

  return { run, setRun, stageStatus, seconds, error, finished: run != null };
}
