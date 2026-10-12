import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/**
 * Compute room-to-room adjacency from the live Revit model and project it as
 * Derived `adjacent_to` edges. Forwards to the `kg_compute_adjacency` socket
 * command (RevitMCPKgCommandSet). Deterministic, idempotent (full replace),
 * Revit-side read-only. Run it after geometry changes to refresh adjacency.
 */
export function registerKgComputeAdjacencyTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_adjacency", "Compute room-to-room adjacency from the live model and project it as Derived adjacent_to edges (Room ↔ Room). GEOMETRIC pass (same implementation as kg_export) probing both sides of every boundary segment; rewrites BOTH adjacent_to and connects (single writer). Deterministic (no LLM), idempotent (full replace each run), Revit-side read-only. Each edge carries boundary_type (wall|separation|mixed), via (mediator node llm_ids), method=geometric and computed_at_turn. Returns { rooms, pairs, connect_pairs, computed_at_turn, adjacencies }. Derived, not live: re-run after geometry edits.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_adjacency", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
