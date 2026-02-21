import { useReducer, useRef, useCallback } from "react";
import { startBulkStream, type SSEEvent } from "@/services/sseService";
import type { BulkItemState } from "@/types/api";

// ─── State ───────────────────────────────────────────────────

export interface BulkStreamState {
  phase: "idle" | "streaming" | "done" | "error";
  jobId: string | null;
  items: BulkItemState[];
  total: number;
  completed: number;
  failed: number;
  progressPct: number;
  error: string | null;
}

const initialState: BulkStreamState = {
  phase: "idle",
  jobId: null,
  items: [],
  total: 0,
  completed: 0,
  failed: 0,
  progressPct: 0,
  error: null,
};

// ─── Actions ─────────────────────────────────────────────────

type Action =
  | { type: "START"; urls: string[] }
  | { type: "JOB_STARTED"; jobId: string }
  | { type: "ITEM_STARTED"; index: number }
  | { type: "ITEM_STEP"; index: number; step: string }
  | { type: "ITEM_COMPLETED"; index: number; success: boolean; result: unknown; error: string }
  | { type: "JOB_PROGRESS"; completed: number; failed: number; progressPct: number }
  | { type: "DONE" }
  | { type: "ERROR"; error: string }
  | { type: "RESET" };

// ─── Reducer ─────────────────────────────────────────────────

function reducer(state: BulkStreamState, action: Action): BulkStreamState {
  switch (action.type) {
    case "START": {
      const items: BulkItemState[] = action.urls.map((url) => ({
        url,
        status: "pending",
        step: null,
        result: null,
        error: null,
      }));
      return { ...initialState, phase: "streaming", items, total: action.urls.length };
    }

    case "JOB_STARTED":
      return { ...state, jobId: action.jobId };

    case "ITEM_STARTED": {
      const items = [...state.items];
      const item = items[action.index];
      if (item) items[action.index] = { ...item, status: "processing", step: "starting" };
      return { ...state, items };
    }

    case "ITEM_STEP": {
      const items = [...state.items];
      const item = items[action.index];
      if (item) items[action.index] = { ...item, step: action.step };
      return { ...state, items };
    }

    case "ITEM_COMPLETED": {
      const items = [...state.items];
      const item = items[action.index];
      if (item) {
        items[action.index] = {
          ...item,
          status: action.success ? "completed" : "failed",
          step: null,
          result: action.success ? (action.result as BulkItemState["result"]) : null,
          error: action.success ? null : action.error,
        };
      }
      return { ...state, items };
    }

    case "JOB_PROGRESS":
      return {
        ...state,
        completed: action.completed,
        failed: action.failed,
        progressPct: action.progressPct,
      };

    case "DONE":
      return { ...state, phase: "done" };

    case "ERROR":
      return { ...state, phase: "error", error: action.error };

    case "RESET":
      return initialState;

    default:
      return state;
  }
}

// ─── Hook ────────────────────────────────────────────────────

export function useBulkStream() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<(() => void) | null>(null);

  const start = useCallback((urls: string[], options?: { publish?: boolean; sellPrice?: number }) => {
    // Cancel any existing stream
    abortRef.current?.();

    dispatch({ type: "START", urls });

    const handleEvent = (e: SSEEvent) => {
      const d = e.data;
      switch (e.event) {
        case "job_started":
          dispatch({ type: "JOB_STARTED", jobId: d.job_id as string });
          break;
        case "item_started":
          dispatch({ type: "ITEM_STARTED", index: d.index as number });
          break;
        case "item_step":
          dispatch({ type: "ITEM_STEP", index: d.index as number, step: d.step as string });
          break;
        case "item_completed":
          dispatch({
            type: "ITEM_COMPLETED",
            index: d.index as number,
            success: d.success as boolean,
            result: d.result,
            error: (d.error as string) ?? "",
          });
          break;
        case "job_progress":
          dispatch({
            type: "JOB_PROGRESS",
            completed: d.completed as number,
            failed: d.failed as number,
            progressPct: d.progress_pct as number,
          });
          break;
        case "job_completed":
          dispatch({
            type: "JOB_PROGRESS",
            completed: d.completed as number,
            failed: d.failed as number,
            progressPct: 100,
          });
          dispatch({ type: "DONE" });
          break;
        // heartbeat and unknown events are ignored
      }
    };

    const handleError = (err: Error) => {
      dispatch({ type: "ERROR", error: err.message });
    };

    const handleDone = () => {
      // Only mark done if not already in error/done state
      // (job_completed event handles the normal done case)
    };

    abortRef.current = startBulkStream(urls, handleEvent, handleError, handleDone, options);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    dispatch({ type: "DONE" });
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    dispatch({ type: "RESET" });
  }, []);

  return { state, start, cancel, reset };
}
