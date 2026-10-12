import { kgSend, kgResult, kgError } from "../kg/socket.js";
import { kgToolsEnabled, logKgModeOnce } from "../kg/mode.js";
/** Attitude of a wall-attached element towards its host. Forwards to `kg_compute_coplanar`. */
export function registerKgComputeCoplanarTool(server) {
    logKgModeOnce();
    if (!kgToolsEnabled())
        return;
    server.tool("kg_compute_coplanar", "Compute the ATTITUDE of each wall-attached element towards its host: Derived coplanar_to_host edges (element -> Wall, N:1) carrying dihedral_deg (angle between the element's dominant planar face and the wall plane, folded to 0..90) and depth_from_host_face_m with datum='host_face' (volume centroid distance from the host FACE on the element's own side). The attribute NAMES ITS DATUM: composition_rules carry a requirement also called coplanar_to_host whose depth is counted from the ROOM BOUNDARY BAND, and on the same niche visual the two read -0.127 m and -0.016..+0.033 m -- reading one for the other inverts the verdict, plus an attitude of parallel (<=12 deg, the validator's own tolerance) / perpendicular (>=78 deg) / oblique / horizontal_face. It does NOT say WHICH wall — `hosts` and `clads_wall` already do, and complementarily (measured: 502 + 1294, zero overlap); it says HOW. The dihedral separates a PANEL lying on the wall from a FIN standing off it, and it is what caught real defects where an element was posed perpendicular to its wall; today the validator recomputes it on every pass and throws it away. Measured on the live solid, per instance: no family store is involved. WARNING: THE DEPTH DOES NOT DETECT A NICHE — an element at the back of a niche is hosted by the thin panel that is itself inside the niche, so it reads flush here; niche depth is measured from the ROOM BOUNDARY (constraint field), a different datum and a separate relation. No dihedral is reported when the dominant face is horizontal, rather than inventing a 90. Refreshes clads_wall first, since most pairs come from it and a Derived layer does not survive a session restart. Deterministic, idempotent full-replace, Revit-side read-only. Returns { pairs, edges, via_hosts, via_clads_wall, skipped_no_solid, skipped_no_wall_line, parallel, perpendicular, oblique, horizontal_face, computed_at_turn }.", {}, async () => {
        try {
            return kgResult(await kgSend("kg_compute_coplanar", {}));
        }
        catch (error) {
            return kgError(error);
        }
    });
}
