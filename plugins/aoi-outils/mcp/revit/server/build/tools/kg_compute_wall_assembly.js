import { z } from "zod";
import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Walls -> the multi-layer build-ups they compose. Forwards to `kg_compute_wall_assembly`. */
export function registerKgComputeWallAssemblyTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_wall_assembly", "Group walls into WALL ASSEMBLIES — the multi-layer build-ups a fit-out is made of, which Revit models only as loose parallel walls. Creates Derived WallAssembly nodes (layer_count, total_thickness_m, length_m, direction, wall_types) and belongs_to_assembly edges (Wall -> WallAssembly, N:1). WHY: a cladding element is attached to ONE wall by clads_wall, chosen as the nearest face — but a bronze lame has 14 to 24 parallel walls within 30 cm of it, layers 2 cm apart, so 'nearest face' is a coin flip. The element does not belong to a layer, it belongs to the BUILD-UP; grouping the layers makes 95% of clad elements see a single assembly instead. Two walls join when they are parallel (|d.d'| >= 0.95), their FACES are within max_face_gap_m (default 0.15 m), and they overlap along the axis by at least 0.10 m; transitive closure. The 0.15 m is calibrated on a PLATEAU, not tuned: resolution goes 53% at 2 cm, 77% at 10 cm, 95% at 15 cm, then flat to 40 cm, and the knee matches the physical recess depth (12-18 cm). It detects a build-up along a RUN (measured 7.5-11.7 m for 0.42-0.73 m of thickness), NOT a 'gorge': the shadow gap is a feature INSIDE an assembly. Curved walls are skipped because their chord lies. An assembly's identity is its layer set, so a re-run reuses the node when that set is unchanged and soft-deletes the ones the model no longer produces. No derived dependency to refresh. Deterministic, idempotent, Revit-side read-only. Returns { walls, assemblies, edges, isolated, max_layers, reused, created, retired_previous, max_face_gap_m, computed_at_turn }.", {
        max_face_gap_m: z
            .number()
            .positive()
            .optional()
            .describe("Override the calibrated 0.15 m face-to-face gap. Provided for RE-MEASURING on a new project (sweep it and look for the plateau), not for tuning until the number looks good."),
    }, async ({ max_face_gap_m }) => {
        try {
            return kgResult(await kgSend("kg_compute_wall_assembly", { max_face_gap_m }));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
