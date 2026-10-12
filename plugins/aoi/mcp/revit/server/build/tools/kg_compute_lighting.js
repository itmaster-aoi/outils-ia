import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Per-room lighting inventory (via host ceiling). Forwards to `kg_compute_lighting`. */
export function registerKgComputeLightingTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_lighting", "Compute the per-room lighting inventory: Derived has_luminaire edges (Room -> ModelElement lighting fixture). THE TEST IS PLANAR AND THE ROOM'S HEIGHT PLAYS NO PART: a fixture is attached when its point falls inside the room's BOUNDARY LOOPS in plan, whatever its z — measured on Pacific Place, 57 of 232 fixtures sit above the rooms' top and are attached all the same. The z only DISAMBIGUATES between candidate rooms, and through the room's FLOOR (Z0), never its ceiling: on stacked levels a downlight belongs to the room immediately below it. Three steps in order: (1) the point falls inside a room in plan; (2) otherwise the nearest room within 0.30 m, for a fixture set against a wall; (3) LAST RESORT ONLY, the host ceiling, and only when that ceiling serves exactly ONE room — the shared-ceiling ambiguity is what produced false attachments. Step 3 therefore almost never fires (via_ceiling = 0 on all six corpus projects, though 204 of 232 fixtures ARE ceiling-hosted): that is the correct behaviour of a last resort, not a defect. An unattached fixture is a PLAN problem — its point falls outside every room outline by more than 0.30 m — never a height problem. Each edge carries family_type, mount (ceiling | wall | free) and the host ceiling ref (RCP plane). Idempotent full-replace, Revit-side read-only. Feeds the ceiling/lighting planner. Requires ceilings computed first (does so at kg_export). Also recomputed at kg_export. Returns { luminaires, edges, rooms, via_ceiling, computed_at_turn }.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_lighting", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
