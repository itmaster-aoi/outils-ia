import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Room -> covering Ceiling (material + height, RCP). Forwards to `kg_compute_ceiling`. */
export function registerKgComputeCeilingTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_ceiling", "Compute ceilings over spaces: Derived has_ceiling edges (Room -> Ceiling) telling which ceiling covers each room, with its finish material, ceiling type and HEIGHT above level (RCP), via a footprint grid probe (GetRoomAtPoint at the room level). A ceiling may span several rooms; a room may carry several ceilings at different heights. Each edge carries material, ceiling_type, height_m, ceiling_area_m2, coverage_ratio, covered_area_m2. Idempotent full-replace, Revit-side read-only. Also recomputed at kg_export. Returns { ceilings, edges, rooms, computed_at_turn }.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_ceiling", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
