import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Room access graph (connects). Forwards to `kg_compute_connects`. */
export function registerKgComputeConnectsTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_connects", "Compute the room access graph: Derived connects edges (Room <-> Room) between rooms one can physically move between. GEOMETRIC pass over the live model (same implementation as kg_export): probes every DOOR, WALL OPENING and ROOM-SEPARATION LINE and QUALIFIES each passage - an opening with a raised sill (imposte) or a passage filled by a fixed panel/gate is a boundary, not a passage. Rewrites BOTH connects and adjacent_to (single writer). Each edge carries via + boundary_type (door|opening|separation|mixed) + method=geometric. Returns { pairs, rooms, adjacent_pairs, passages, separations_filled, openings_rejected_sill, openings_filled, computed_at_turn, connections }.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_connects", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
