import { z } from "zod";
import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Live layout constraint field (bands/clearances/corridors/focals). Forwards to `kg_constraint_field`. */
export function registerKgConstraintFieldTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_constraint_field", "Serve the layout CONSTRAINT FIELD LIVE (placeable wall bands, door-swing clearances, connects corridors, focal points, orientation field, per-room coverage gaps) in the response instead of the dev sidecar — the in-session transport the layout GENERATOR agent consumes. Mirrors the ribbon command's prep (reconcile → refresh connects/adjacency → refresh containment → compute the field). Frame = model metres; each room carries level_elevation_m so an [x,y] lifts to a placement point. Revit-side read-only. Returns { field, rooms, computed_at_turn } where field is the full constraint_field document.", {
        room_id: z
            .string()
            .optional()
            .describe("Optional room to filter to — the KG llm id (e.g. room_008) or revit_<id>. Omit for all rooms."),
    }, async (args) => {
        try {
            return kgResult(await kgSend("kg_constraint_field", args));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
