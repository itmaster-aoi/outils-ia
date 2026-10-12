import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Room -> finish Floor surfacing / zoning. Forwards to `kg_compute_floor_finish`. */
export function registerKgComputeFloorFinishTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_floor_finish", "Compute floor finish / zoning: Derived has_floor_finish edges (Room -> Floor) telling which FINISH floors surface each room and by how much. Type-level finish-vs-slab discrimination (thin covering vs structural slab, from the compound structure — no name lexicon), then a footprint grid probe (GetRoomAtPoint) attaching a finish floor to EVERY room it covers (one floor may span several rooms; a room carries several finishes = zoning). Each edge carries material, floor_type, floor_area_m2, coverage_ratio, covered_area_m2. Idempotent full-replace, Revit-side read-only. Feeds planFloor with real finishes/zones. Also recomputed at kg_export. Returns { finish_floors, edges, rooms, computed_at_turn }.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_floor_finish", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
