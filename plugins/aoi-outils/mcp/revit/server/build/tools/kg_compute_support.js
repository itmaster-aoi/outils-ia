import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Accessory -> the carrier it RESTS ON. Forwards to `kg_compute_support`. */
export function registerKgComputeSupportTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_support", "Compute the SUPPORT relation: Derived stacked edges (ModelElement -> ModelElement, DIRECTED child -> carrier, N:1) telling what each accessory RESTS ON — a desk pad and a lamp on a table, a display panel on a showcase tray, a seat module on a counter. Reads the LIVE model: an export carries no absolute altitude (family frames are measured from each family's own insertion point), so this cannot be mined offline. THE EDGE STORES THE FACT, NOT THE ALTITUDE — no instance z enters the KG; the seat is re-derived from the carrier at placement time. Contact = carrier top within 3 cm of the child's base AND >= 90% of the child's footprint covered (90%, not strict inclusion: a lamp legitimately overhangs its table). The COMPOSITION GRAMMAR is excluded upstream, and that exclusion is part of the definition: raw contact detection is dominated by cladding modules stacked in courses (measured on a fit-out: 499 raw contacts -> ~12 edges). Three KG-native or structural filters, never a copy of a family lexicon: the child or carrier carries clads_wall/has_luminaire; both ends are the same family; one carrier bears 4 or more identical children. Refreshes its own dependencies first (clads_wall, has_luminaire) because those ARE the grammar flag and neither survives a session restart. Deterministic, idempotent full-replace, Revit-side read-only. Returns { candidates, raw_contacts, grammar_flagged, rejected_grammar, rejected_self_stack, rejected_course, edges, carriers, computed_at_turn } — read grammar_flagged before trusting edges: 0 on a large contact set means the exclusion could not do its job.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_support", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
