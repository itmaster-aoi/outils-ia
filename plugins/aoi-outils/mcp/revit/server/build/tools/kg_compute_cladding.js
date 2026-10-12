import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Unhosted 3D cladding -> inferred host Wall. Forwards to `kg_compute_cladding`. */
export function registerKgComputeCladdingTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_cladding", "Compute wall cladding: Derived clads_wall edges (ModelElement -> Wall) inferring the host wall of each UNHOSTED 3D cladding element (flutings, reveals, bronze lames, LED corniches) by perpendicular proximity to a wall face, along the wall's extent. Drops 2D view-specific detail symbols (BreakLine) and already-hosted elements. Non-lexical, deterministic, idempotent full-replace, Revit-side read-only. Each edge carries face_distance_m. Gives planCladding a real per-wall assignment instead of an ordering heuristic. Also recomputed at kg_export. Returns { candidates, edges, walls, computed_at_turn }.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_cladding", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
