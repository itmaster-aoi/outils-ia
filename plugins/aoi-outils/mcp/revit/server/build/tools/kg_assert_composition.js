import { z } from "zod";
import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/**
 * ASSERT a designated composition. The counterpart of the kg_compute_* computers, for
 * assemblies no computer can derive: we have the recipe, not the discriminant.
 * Forwards to the `kg_assert_composition` command.
 */
export function registerKgAssertCompositionTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_assert_composition", "ASSERT a designated composition into the KG — the counterpart of the kg_compute_* computers, for assemblies no computer can find (we have the recipe, not the discriminant). Declared catalogue: threshold, wall_tableau, wall_step, wallstep_positif, wallstep_negatif, room, wall_assembly, vase_group, modular_bookcase, recessed_bookcase, niche, sideboard, ecrin_showcase, box_wallshowcase, console_group, watchbar, seating_group, visuals_panel, groupe_vente_3p, coin_miroir, axis. EXACTLY ONE member must carry the type's identity role. Every member goes through CompositionWriter.AddMember, so a role foreign to the type is REFUSED and counted in members_refused — which must be 0; a non-zero value is a defect, not a fact. A composition of the same type already carrying the same identity member is REUSED, never duplicated, and members it no longer names are removed. revit_ids resolving to no node are listed in unresolved — the usual cause is a non-primary design option, which the projection drops.", {
        type_name: z
            .string()
            .describe("Declared composition type. The vocabulary is CLOSED: an unknown name is refused, never created on the fly."),
        members: z
            .array(z.object({
            revit_id: z.number().optional().describe("Revit ElementId of the member."),
            llm_id: z.string().optional().describe("KG llm_id — use this for a member that is itself a Composition (e.g. bookcase_tableau, ecrin_box, axis_term)."),
            role: z.string().describe("The role this member plays in the composition."),
        }))
            .min(1)
            .describe("The members, each with revit_id OR llm_id, plus its role."),
        attrs: z
            .record(z.any())
            .optional()
            .describe("Attributes of the composition — notably `datum`, which is NOT derivable from geometry and must be carried."),
    }, async (args) => {
        try {
            return kgResult(await kgSend("kg_assert_composition", args));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
