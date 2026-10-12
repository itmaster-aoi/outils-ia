import { z } from "zod";
import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Reconcile the KG to the live Revit doc. Forwards to the `kg_resolve_drift` command. */
export function registerKgResolveDriftTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_resolve_drift", "Align the KG v2 projection to the live Revit document per entry: missing_in_kg → project the element; attrs_diverged → overwrite KG attrs; orphan_kg_node → soft-delete; tombstoned_but_live → resurrect + re-sync. F2 annotations and bootstrap nodes are preserved. P5: an orphan and a newly projected node of the same type with EXACTLY equal attrs (1:1) are declared successors (replaced_by edge, successions_written / successions_ambiguous) - composition keys resolve through that chain, so redrawing an anchor no longer loses what a human authored on its compositions. A non-dry-run REQUIRES confirm=\"align-to-revit\".", {
        kinds: z
            .array(z.string())
            .optional()
            .describe("Restrict to these drift kinds (missing_in_kg, attrs_diverged, orphan_kg_node, tombstoned_but_live)."),
        node_type: z.string().optional().describe("Restrict reconciliation to one node type."),
        dry_run: z
            .boolean()
            .optional()
            .describe("Preview the plan without mutating (default false)."),
        confirm: z
            .string()
            .optional()
            .describe("Must equal \"align-to-revit\" for a non-dry-run to proceed."),
    }, async (args) => {
        try {
            return kgResult(await kgSend("kg_resolve_drift", args));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
