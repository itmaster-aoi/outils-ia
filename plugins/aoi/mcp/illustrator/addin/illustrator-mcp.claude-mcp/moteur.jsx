// Moteur illustrator-mcp : ExtendScript (ES3) chargé une fois dans Illustrator, gardé dans $.global.__aimcp.
// Entrée unique : __aimcp.appel(commande, paramètres) rend un texte JSON {ok, r} ou {ok:false, e:{code, message}}.
// Le même fichier sert au canal COM (serveur Python) et au panneau CEP (evalScript).
//
// Coordonnées publiques : relatives au plan de travail, Y vers le bas, unité des règles du document.
// bounds = [haut, gauche, bas, droite]. Illustrator travaille en points, Y vers le haut : le moteur convertit.
$.global.__aimcp = (function () {
    var VERSION = '0.1.0';
    var REF = /^\$(\d+)\.([A-Za-z_]\w*)$/;

    // ---------------------------------------------------------------- outils de base
    function erreur(code, message) { var e = new Error(message); e.code = code; return e; }
    function estTableau(v) { return v instanceof Array; }
    function arr(v) { return Math.round(v * 100) / 100; }

    function txt(s) {
        var i, k, o = [];
        s = String(s);
        for (i = 0; i < s.length; i++) {
            k = s.charCodeAt(i);
            if (k === 34) o.push('\\"');
            else if (k === 92) o.push('\\\\');
            else if (k === 10) o.push('\\n');
            else if (k === 13) o.push('\\r');
            else if (k === 9) o.push('\\t');
            else if (k < 32 || k === 8232 || k === 8233) o.push('\\u' + ('0000' + k.toString(16)).slice(-4));
            else o.push(s.charAt(i));
        }
        return '"' + o.join('') + '"';
    }
    function json(v) {
        var i, k, t = [];
        if (v === null || v === undefined) return 'null';
        if (typeof v === 'number') return isFinite(v) ? String(v) : 'null';
        if (typeof v === 'boolean') return String(v);
        if (typeof v === 'string') return txt(v);
        if (estTableau(v)) {
            for (i = 0; i < v.length; i++) t.push(json(v[i]));
            return '[' + t.join(',') + ']';
        }
        if (typeof v === 'object') {
            for (k in v) if (v.hasOwnProperty(k) && v[k] !== undefined) t.push(txt(k) + ':' + json(v[k]));
            return '{' + t.join(',') + '}';
        }
        return txt(v);
    }
    // Retire les valeurs nulles de fin d'une ligne compacte.
    function ligne(l) { while (l.length && (l[l.length - 1] === null || l[l.length - 1] === undefined)) l.pop(); return l; }

    // ---------------------------------------------------------------- contexte du document
    var ctx = null; // {d, k, pl:[artboardRect]} : refait à chaque appel et après un changement de plans de travail

    function facteur(d) {
        var u = d.rulerUnits;
        if (u === RulerUnits.Millimeters) return {k: 72 / 25.4, u: 'mm'};
        if (u === RulerUnits.Centimeters) return {k: 72 / 2.54, u: 'cm'};
        if (u === RulerUnits.Inches) return {k: 72, u: 'in'};
        if (u === RulerUnits.Picas) return {k: 12, u: 'pc'};
        if (u === RulerUnits.Pixels) return {k: 1, u: 'px'};
        return {k: 1, u: 'pt'};
    }
    function C() {
        var d, f, i;
        if (ctx) return ctx;
        if (!app.documents.length) throw erreur('aucun_document', 'Aucun document ouvert dans Illustrator.');
        d = app.activeDocument; f = facteur(d);
        ctx = {d: d, k: f.k, u: f.u, pl: []};
        for (i = 0; i < d.artboards.length; i++) ctx.pl.push(d.artboards[i].artboardRect);
        return ctx;
    }
    // Rang (0 = premier) du plan de travail : numéro à partir de 1, ou nom.
    function planche(ref) {
        var c = C(), n, i;
        if (ref === undefined || ref === null || ref === '') return c.d.artboards.getActiveArtboardIndex();
        n = Number(ref);
        if (!isNaN(n) && n >= 1 && n <= c.pl.length && n === Math.floor(n)) return n - 1;
        for (i = 0; i < c.pl.length; i++) if (c.d.artboards[i].name === String(ref)) return i;
        throw erreur('plan_inconnu', 'Plan de travail inconnu : ' + ref + ' (le document en a ' + c.pl.length + ')');
    }
    // bounds publics -> {l, t, w, h} en points du document.
    function versDoc(a, b) {
        var c = C(), r = c.pl[a];
        if (!estTableau(b) || b.length !== 4) throw erreur('parametres', 'bounds = [haut, gauche, bas, droite]');
        return {l: r[0] + b[1] * c.k, t: r[1] - b[0] * c.k, w: (b[3] - b[1]) * c.k, h: (b[2] - b[0]) * c.k};
    }
    function pointDoc(a, xy) {
        var c = C(), r = c.pl[a];
        if (!estTableau(xy) || xy.length !== 2) throw erreur('parametres', 'point = [x, y]');
        return [r[0] + xy[0] * c.k, r[1] - xy[1] * c.k];
    }
    // Bornes [gauche, haut, droite, bas] en points. Groupe d'écrêtage : bornes du masque.
    function bornes(it) {
        var i, n;
        if (it.typename === 'GroupItem' && it.clipped) {
            n = it.pageItems.length;
            for (i = 0; i < n; i++) if (it.pageItems[i].typename === 'PathItem' && it.pageItems[i].clipping) return it.pageItems[i].geometricBounds;
        }
        return it.geometricBounds;
    }
    // Plan de travail qui contient le centre de l'objet (0 = premier), ou -1.
    function plancheDe(g) {
        var c = C(), x = (g[0] + g[2]) / 2, y = (g[1] + g[3]) / 2, i, r;
        for (i = 0; i < c.pl.length; i++) { r = c.pl[i]; if (x >= r[0] && x <= r[2] && y <= r[1] && y >= r[3]) return i; }
        return -1;
    }
    function publics(g, a) {
        var c = C(), r = c.pl[a < 0 ? 0 : a];
        return [arr((r[1] - g[1]) / c.k), arr((g[0] - r[0]) / c.k), arr((r[1] - g[3]) / c.k), arr((g[2] - r[0]) / c.k)];
    }

    function objet(id) {
        try { return C().d.getPageItemFromUuid(String(id)); }
        catch (e) { throw erreur('introuvable', 'Objet introuvable : ' + id + ' (un id vaut pour la session ; refaites snapshot)'); }
    }
    // Cible d'une commande : id, ou ids:[...].
    function cibles(p) {
        var l = [], i, src = p.ids !== undefined ? p.ids : (p.cible !== undefined ? p.cible : p.id);
        if (src === undefined || src === null) throw erreur('parametres', 'il faut id ou ids');
        if (!estTableau(src)) src = [src];
        for (i = 0; i < src.length; i++) l.push(objet(src[i]));
        return l;
    }
    function calque(nom) {
        try { return C().d.layers.getByName(String(nom)); }
        catch (e) { throw erreur('calque_inconnu', 'Calque inconnu : ' + nom); }
    }
    // "none", "#rrggbb", [r,g,b] (0-255), [c,m,y,k] (0-100), ou nom de nuance.
    function couleur(v) {
        var c, n;
        if (v === 'none' || v === null) return new NoColor();
        if (typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v)) {
            n = parseInt(v.substr(1), 16);
            v = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
        }
        if (estTableau(v) && v.length === 3) { c = new RGBColor(); c.red = v[0]; c.green = v[1]; c.blue = v[2]; return c; }
        if (estTableau(v) && v.length === 4) { c = new CMYKColor(); c.cyan = v[0]; c.magenta = v[1]; c.yellow = v[2]; c.black = v[3]; return c; }
        try { return C().d.swatches.getByName(String(v)).color; }
        catch (e) { throw erreur('couleur', 'Couleur inconnue : ' + v + ' ("none", "#rrggbb", [r,g,b], [c,m,y,k] ou nom de nuance)'); }
    }
    function fichier(chemin, doitExister) {
        var f = new File(String(chemin));
        if (doitExister && !f.exists) throw erreur('fichier_absent', 'Fichier absent : ' + chemin);
        if (!doitExister && f.parent && !f.parent.exists && !f.parent.create()) throw erreur('dossier', 'Dossier impossible à créer : ' + f.parent.fsName);
        return f;
    }

    // Propriétés communes : name, fill, stroke, stroke_width (points), opacity, layer, locked, hidden, size, font.
    function appliquer(it, p) {
        var t = it.typename, ca;
        if (p.layer !== undefined) it.move(calque(p.layer), ElementPlacement.PLACEATBEGINNING);
        if (p.name !== undefined) it.name = String(p.name);
        if (p.opacity !== undefined) it.opacity = Number(p.opacity);
        if (p.fill !== undefined || p.stroke !== undefined || p.stroke_width !== undefined) {
            if (t === 'CompoundPathItem') it = it.pathItems[0];
            if (t === 'TextFrame') {
                ca = it.textRange.characterAttributes;
                if (p.fill !== undefined) ca.fillColor = couleur(p.fill);
                if (p.stroke !== undefined) ca.strokeColor = couleur(p.stroke);
                if (p.stroke_width !== undefined) ca.strokeWeight = Number(p.stroke_width);
            } else if (t === 'PathItem' || t === 'CompoundPathItem') {
                if (p.fill !== undefined) { it.filled = p.fill !== 'none' && p.fill !== null; if (it.filled) it.fillColor = couleur(p.fill); }
                if (p.stroke !== undefined) { it.stroked = p.stroke !== 'none' && p.stroke !== null; if (it.stroked) it.strokeColor = couleur(p.stroke); }
                if (p.stroke_width !== undefined) { it.stroked = true; it.strokeWidth = Number(p.stroke_width); }
            } else throw erreur('parametres', 'fill et stroke : tracé ou texte seulement, pas ' + t);
        }
        if (p.size !== undefined || p.font !== undefined) {
            if (t !== 'TextFrame') throw erreur('parametres', 'size et font : texte seulement');
            ca = it.textRange.characterAttributes;
            if (p.size !== undefined) ca.size = Number(p.size);
            if (p.font !== undefined) {
                try { ca.textFont = app.textFonts.getByName(String(p.font)); }
                catch (e) { throw erreur('police', 'Police inconnue : ' + p.font + ' (nom PostScript, par exemple MyriadPro-Regular)'); }
            }
        }
        if (p.hidden !== undefined) it.hidden = !!p.hidden;
        if (p.locked !== undefined) it.locked = !!p.locked;
        return it;
    }

    // Met les bornes de l'objet à {l, t, w, h} (points du document).
    function borner(it, r) {
        var g, tp;
        if (it.typename === 'TextFrame') {
            if (it.kind === TextType.AREATEXT) { // changer le tracé du bloc, pas l'échelle du texte
                tp = it.textPath;
                if (r.w > 0) tp.width = r.w;
                if (r.h > 0) tp.height = r.h;
                tp.left = r.l; tp.top = r.t;
                return;
            }
            g = it.geometricBounds; it.translate(r.l - g[0], r.t - g[1]); // texte de point : déplacement seul
            return;
        }
        if (it.typename === 'GroupItem' && it.clipped) {
            g = bornes(it);
            if (g[2] - g[0] > 0 && g[1] - g[3] > 0 && r.w > 0 && r.h > 0) it.resize(r.w / (g[2] - g[0]) * 100, r.h / (g[1] - g[3]) * 100);
            g = bornes(it); it.translate(r.l - g[0], r.t - g[1]);
            return;
        }
        if (r.w > 0 && it.width > 0) it.width = r.w;
        if (r.h > 0 && it.height > 0) it.height = r.h;
        g = it.geometricBounds; it.translate(r.l - g[0], r.t - g[1]);
    }

    // Place une image dans {l, t, w, h}. fit : proportional (défaut), stretch, fill (écrêtage). Rend l'objet à citer.
    function placer(f, r, fit) {
        var d = C().d, it = d.placedItems.add(), w0, h0, s, g, m;
        it.file = f;
        if (!r) return it;
        if (r.w === undefined) { g = it.geometricBounds; it.translate(r.l - g[0], r.t - g[1]); return it; }
        w0 = it.width; h0 = it.height;
        if (fit === 'stretch') { it.width = r.w; it.height = r.h; }
        else {
            s = fit === 'fill' ? Math.max(r.w / w0, r.h / h0) : Math.min(r.w / w0, r.h / h0);
            it.width = w0 * s; it.height = h0 * s;
        }
        g = it.geometricBounds;
        it.translate(r.l + (r.w - it.width) / 2 - g[0], r.t - (r.h - it.height) / 2 - g[1]);
        if (fit !== 'fill') return it;
        g = d.groupItems.add();
        m = d.pathItems.rectangle(r.t, r.l, r.w, r.h);
        it.move(g, ElementPlacement.PLACEATEND);
        m.move(g, ElementPlacement.PLACEATBEGINNING);
        m.clipping = true; g.clipped = true;
        return g;
    }

    // ---------------------------------------------------------------- lecture
    var CODES = {PathItem: 'P', CompoundPathItem: 'C', TextFrame: 'T', PlacedItem: 'I', RasterItem: 'R', GroupItem: 'G', SymbolItem: 'S', MeshItem: 'M'};
    var COLS_ITEMS = ['id', 't', 'a', 'b', 'l', 'n', 'x', 'f', 'g', 's'];
    var COLS_LINKS = ['id', 'n', 'd', 'a', 's'];

    // "1-3,5" -> table {rang: true} (rang à partir de 0), ou null pour tout.
    function plage(texte, max) {
        var o = {}, parts, i, m, a, b, j;
        if (texte === undefined || texte === null || texte === '') return null;
        parts = String(texte).split(',');
        for (i = 0; i < parts.length; i++) {
            m = /^\s*(\d+)\s*(?:-\s*(\d+))?\s*$/.exec(parts[i]);
            if (!m) throw erreur('parametres', 'plage illisible : ' + texte + ' (exemples : "2", "1-3", "1,4")');
            a = Number(m[1]); b = m[2] ? Number(m[2]) : a;
            for (j = a; j <= b && j <= max; j++) o[j - 1] = true;
        }
        return o;
    }
    function nomFichier(it) { try { return it.file ? it.file.fsName : null; } catch (e) { return undefined; } }

    function snapshot(p) {
        var c = C(), d = c.d, out = {}, secs = {}, i, s, l, r;
        s = p.sections && p.sections.length ? p.sections : ['doc', 'artboards'];
        for (i = 0; i < s.length; i++) secs[s[i]] = true;
        if (secs.doc) {
            out.doc = {name: d.name, path: String(d.path) ? d.fullName.fsName : null, saved: d.saved, u: c.u,
                color: d.documentColorSpace === DocumentColorSpace.CMYK ? 'cmyk' : 'rgb', items: d.pageItems.length, layers: []};
            for (i = 0; i < d.layers.length; i++) {
                l = d.layers[i];
                out.doc.layers.push(ligne([l.name, l.pageItems.length, !l.visible ? 'H' : (l.locked ? 'L' : null)]));
            }
        }
        if (secs.artboards) {
            out.artboards = [];
            for (i = 0; i < c.pl.length; i++) { r = c.pl[i]; out.artboards.push([i + 1, d.artboards[i].name, arr((r[2] - r[0]) / c.k), arr((r[1] - r[3]) / c.k)]); }
            out.active = d.artboards.getActiveArtboardIndex() + 1;
        }
        if (secs.items) lireItems(p, out);
        if (secs.links) lireLiens(out);
        return out;
    }
    function lireItems(p, out) {
        var c = C(), d = c.d, its, n, i, it, t, g, a, par, etat, f, x, nomC, rang, k;
        var veutPl = plage(p.artboards, c.pl.length), veutCalque = p.layer, noms = [], idx = {}, lignes = [];
        var debut = p.offset || 0, lim = p.limit || 300, vus = 0, suite = null;
        if (p.ids && p.ids.length) { its = []; for (i = 0; i < p.ids.length; i++) its.push(objet(p.ids[i])); }
        else its = d.pageItems;
        n = its.length;
        for (i = 0; i < n; i++) {
            it = its[i]; t = it.typename; par = it.parent.typename;
            if (par === 'CompoundPathItem') continue; // sous-tracés : bruit
            nomC = it.layer.name;
            if (veutCalque !== undefined && veutCalque !== null && nomC !== String(veutCalque)) continue;
            g = bornes(it); a = plancheDe(g);
            if (veutPl && !veutPl[a]) continue;
            if (vus++ < debut) continue;
            if (lignes.length >= lim) { suite = debut + lim; break; }
            rang = idx[nomC];
            if (rang === undefined) { rang = idx[nomC] = noms.length; noms.push(nomC); }
            x = null; f = null;
            if (t === 'TextFrame') { x = it.contents; if (x.length > 40) x = x.substr(0, 40) + '…'; x = x.replace(/\r/g, '\n'); }
            else if (t === 'PlacedItem') { f = nomFichier(it); f = f === undefined ? '?' : (f ? new File(f).name : null); if (f) f = decodeURI(f); }
            etat = it.hidden ? 'H' : (it.locked ? 'L' : null);
            lignes.push(ligne([it.uuid, CODES[t] || 'X', a + 1, publics(g, a), rang, it.name || null, x, f, par === 'GroupItem' ? it.parent.uuid : null, etat]));
        }
        out.cols = COLS_ITEMS; out.layers = noms; out.items = lignes;
        if (suite !== null) out.next = suite;
    }
    function lireLiens(out) {
        var c = C(), d = c.d, n = d.placedItems.length, i, it, f, dirs = [], idx = {}, dos, rang, lignes = [];
        for (i = 0; i < n; i++) {
            it = d.placedItems[i]; f = nomFichier(it);
            if (!f) { lignes.push([it.uuid, it.name || null, null, plancheDe(bornes(it)) + 1, 'missing']); continue; }
            f = new File(f); dos = f.parent.fsName; rang = idx[dos];
            if (rang === undefined) { rang = idx[dos] = dirs.length; dirs.push(dos); }
            lignes.push(ligne([it.uuid, decodeURI(f.name), rang, plancheDe(bornes(it)) + 1, f.exists ? null : 'missing']));
        }
        out.link_cols = COLS_LINKS; out.dirs = dirs; out.links = lignes;
    }

    // ---------------------------------------------------------------- commandes de lot
    // Chaque commande : {req: [paramètres obligatoires], run: function (p)}.
    var T = {};

    T['new_document'] = {req: ['width', 'height'], run: function (p) {
        var pr = new DocumentPreset(), u = String(p.units || 'mm'), k, cs, d;
        var U = {mm: [RulerUnits.Millimeters, 72 / 25.4], cm: [RulerUnits.Centimeters, 72 / 2.54], 'in': [RulerUnits.Inches, 72], pt: [RulerUnits.Points, 1], px: [RulerUnits.Pixels, 1]};
        if (!U[u]) throw erreur('parametres', 'units : mm, cm, in, pt ou px');
        k = U[u][1]; cs = p.color === 'rgb' ? DocumentColorSpace.RGB : DocumentColorSpace.CMYK;
        pr.units = U[u][0]; pr.width = p.width * k; pr.height = p.height * k; pr.numArtboards = p.artboards || 1; pr.colorMode = cs;
        if (p.name) pr.title = String(p.name);
        d = app.documents.addDocument(cs, pr); ctx = null;
        return {name: d.name, artboards: d.artboards.length};
    }};
    T['open_document'] = {req: ['path'], run: function (p) {
        var d = app.open(fichier(p.path, true)); ctx = null;
        return {name: d.name, artboards: d.artboards.length};
    }};
    T['create_shape'] = {req: [], run: function (p) {
        var c = C(), a = planche(p.artboard), kind = p.kind || 'rect', r, it, pts = [], i;
        if (kind === 'path') {
            if (!estTableau(p.points) || p.points.length < 2) throw erreur('parametres', 'path : points = [[x,y], ...], 2 points au moins');
            for (i = 0; i < p.points.length; i++) pts.push(pointDoc(a, p.points[i]));
            it = c.d.pathItems.add(); it.setEntirePath(pts); it.closed = !!p.closed;
            if (!p.closed && p.fill === undefined) it.filled = false;
        } else {
            r = versDoc(a, p.bounds);
            if (kind === 'rect') it = c.d.pathItems.rectangle(r.t, r.l, r.w, r.h);
            else if (kind === 'ellipse') it = c.d.pathItems.ellipse(r.t, r.l, r.w, r.h);
            else if (kind === 'line') { it = c.d.pathItems.add(); it.setEntirePath([[r.l, r.t], [r.l + r.w, r.t - r.h]]); it.filled = false; }
            else throw erreur('parametres', 'kind : rect, ellipse, line ou path');
        }
        appliquer(it, p);
        return {id: it.uuid};
    }};
    T['create_text'] = {req: ['text'], run: function (p) {
        var c = C(), a = planche(p.artboard), r, it;
        if (p.bounds) { r = versDoc(a, p.bounds); it = c.d.textFrames.areaText(c.d.pathItems.rectangle(r.t, r.l, r.w, r.h)); }
        else if (p.at) it = c.d.textFrames.pointText(pointDoc(a, p.at));
        else throw erreur('parametres', 'il faut bounds (bloc) ou at:[x,y] (texte de point, y = ligne de base)');
        it.contents = String(p.text).replace(/\n/g, '\r');
        appliquer(it, p);
        return {id: it.uuid};
    }};
    T['place_image'] = {req: ['path'], run: function (p) {
        var a = planche(p.artboard), r = null, it, q;
        if (p.bounds) r = versDoc(a, p.bounds);
        else if (p.at) { q = pointDoc(a, p.at); r = {l: q[0], t: q[1]}; }
        it = placer(fichier(p.path, true), r, p.fit);
        appliquer(it, {name: p.name, layer: p.layer});
        return {id: it.uuid};
    }};
    T['grid'] = {req: ['area', 'rows', 'cols'], run: function (p) {
        var c = C(), a = planche(p.artboard), z = versDoc(a, p.area), gap = (p.gap || 0) * c.k, ids = [], i, j, n = 0, it, r, f;
        var w = (z.w - gap * (p.cols - 1)) / p.cols, h = (z.h - gap * (p.rows - 1)) / p.rows, total = p.rows * p.cols;
        if (p.images) { for (i = 0; i < p.images.length; i++) fichier(p.images[i], true); total = Math.min(total, p.images.length); }
        for (i = 0; i < p.rows && n < total; i++) for (j = 0; j < p.cols && n < total; j++, n++) {
            r = {l: z.l + j * (w + gap), t: z.t - i * (h + gap), w: w, h: h};
            if (p.images) it = placer(new File(String(p.images[n])), r, p.fit || 'fill');
            else if (p.kind === 'text') it = c.d.textFrames.areaText(c.d.pathItems.rectangle(r.t, r.l, r.w, r.h));
            else it = c.d.pathItems.rectangle(r.t, r.l, r.w, r.h);
            appliquer(it, {name: p.name ? p.name + ' ' + (n + 1) : undefined, layer: p.layer, fill: p.images || p.kind === 'text' ? undefined : p.fill, stroke: p.images || p.kind === 'text' ? undefined : p.stroke});
            ids.push(it.uuid);
        }
        return {ids: ids};
    }};
    T['set_text'] = {req: ['id', 'text'], run: function (p) {
        var it = objet(p.id);
        if (it.typename !== 'TextFrame') throw erreur('parametres', 'set_text : l\'objet ' + p.id + ' n\'est pas un texte');
        it.contents = String(p.text).replace(/\n/g, '\r');
    }};
    T['set_bounds'] = {req: ['id', 'bounds'], run: function (p) {
        var it = objet(p.id), a = p.artboard !== undefined ? planche(p.artboard) : plancheDe(bornes(it));
        borner(it, versDoc(a < 0 ? 0 : a, p.bounds));
    }};
    T['set_props'] = {req: [], run: function (p) {
        var l = cibles(p), i;
        for (i = 0; i < l.length; i++) appliquer(l[i], p);
        return {n: l.length};
    }};
    T['move'] = {req: [], run: function (p) {
        var c = C(), l = cibles(p), i, g, a, q;
        if (!p.by && !p.to) throw erreur('parametres', 'il faut by:[dx,dy] ou to:[x,y]');
        for (i = 0; i < l.length; i++) {
            if (p.by) { l[i].translate(p.by[0] * c.k, -p.by[1] * c.k); continue; }
            g = bornes(l[i]); a = p.artboard !== undefined ? planche(p.artboard) : plancheDe(g);
            q = pointDoc(a < 0 ? 0 : a, p.to); l[i].translate(q[0] - g[0], q[1] - g[1]);
        }
        return {n: l.length};
    }};
    T['duplicate'] = {req: ['id'], run: function (p) {
        var c = C(), it = objet(p.id), n = p.count || 1, by = p.by || [0, 0], ids = [], i, x;
        for (i = 1; i <= n; i++) { x = it.duplicate(); x.translate(i * by[0] * c.k, -i * by[1] * c.k); ids.push(x.uuid); }
        return {ids: ids};
    }};
    T['delete_item'] = {req: [], run: function (p) {
        var l = cibles(p), i;
        for (i = l.length - 1; i >= 0; i--) l[i].remove();
        return {n: l.length};
    }};
    T['group'] = {req: ['ids'], run: function (p) {
        var l = cibles(p), g = C().d.groupItems.add(), i;
        for (i = 0; i < l.length; i++) l[i].move(g, ElementPlacement.PLACEATEND);
        if (p.name) g.name = String(p.name);
        return {id: g.uuid};
    }};
    T['order'] = {req: ['to'], run: function (p) {
        var Z = {front: ZOrderMethod.BRINGTOFRONT, back: ZOrderMethod.SENDTOBACK, forward: ZOrderMethod.BRINGFORWARD, backward: ZOrderMethod.SENDBACKWARD};
        var l = cibles(p), i;
        if (!Z[p.to]) throw erreur('parametres', 'to : front, back, forward ou backward');
        for (i = 0; i < l.length; i++) l[i].zOrder(Z[p.to]);
        return {n: l.length};
    }};
    T['select'] = {req: [], run: function (p) {
        var d = C().d, l = p.id === undefined && p.ids === undefined ? [] : cibles(p);
        d.selection = l.length ? l : null;
        return {n: l.length};
    }};
    T['add_artboard'] = {req: ['width', 'height'], run: function (p) {
        var c = C(), d = c.d, i, droite = -1e9, haut = 0, gap = (p.gap === undefined ? 20 / c.k : p.gap) * c.k, a;
        for (i = 0; i < c.pl.length; i++) if (c.pl[i][2] > droite) { droite = c.pl[i][2]; haut = c.pl[i][1]; }
        a = d.artboards.add([droite + gap, haut, droite + gap + p.width * c.k, haut - p.height * c.k]);
        if (p.name) a.name = String(p.name);
        ctx = null;
        return {artboard: d.artboards.length};
    }};
    T['set_artboard'] = {req: ['artboard'], run: function (p) {
        var c = C(), i = planche(p.artboard), a = c.d.artboards[i], r = a.artboardRect;
        if (p.name !== undefined) a.name = String(p.name);
        if (p.width !== undefined || p.height !== undefined) {
            a.artboardRect = [r[0], r[1], p.width !== undefined ? r[0] + p.width * c.k : r[2], p.height !== undefined ? r[1] - p.height * c.k : r[3]];
        }
        if (p.active) c.d.artboards.setActiveArtboardIndex(i);
        ctx = null;
    }};
    T['add_layer'] = {req: ['name'], run: function (p) {
        var l = C().d.layers.add(); l.name = String(p.name);
        return {layer: l.name};
    }};
    T['change_text'] = {req: ['find'], run: function (p) {
        var d = C().d, n = 0, i, j, k, s, texte, re, m, pos, rep, ch;
        var motif = p.regex ? String(p.find) : String(p.find).replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&');
        var drapeaux = p.ignore_case ? 'gi' : 'g', un = new RegExp(motif, p.ignore_case ? 'i' : '');
        for (i = 0; i < d.stories.length; i++) {
            s = d.stories[i]; texte = s.textRange.contents; re = new RegExp(motif, drapeaux); pos = [];
            while ((m = re.exec(texte)) !== null) { if (!m[0].length) { re.lastIndex++; continue; } pos.push([m.index, m[0]]); }
            n += pos.length;
            if (p.change === undefined || p.change === null) continue;
            ch = s.textRange.characters;
            for (j = pos.length - 1; j >= 0; j--) { // de la fin vers le début : les rangs restent justes
                rep = pos[j][1].replace(un, String(p.change)).replace(/\n/g, '\r');
                for (k = pos[j][0] + pos[j][1].length - 1; k > pos[j][0]; k--) ch[k].remove();
                if (rep === '') ch[pos[j][0]].remove(); else ch[pos[j][0]].contents = rep;
            }
        }
        return {n: n};
    }};
    T['relink'] = {req: ['path'], run: function (p) {
        var d = C().d, f = fichier(p.path, true), ids = [], i, it, nom;
        if (p.id !== undefined) { it = objet(p.id); if (it.typename !== 'PlacedItem') throw erreur('parametres', 'relink : l\'objet ' + p.id + ' n\'est pas une image liée'); it.file = f; return {n: 1, ids: [it.uuid]}; }
        if (p.name === undefined) throw erreur('parametres', 'il faut id, ou name (nom de fichier : tous les liens de ce nom)');
        for (i = 0; i < d.placedItems.length; i++) {
            it = d.placedItems[i]; nom = nomFichier(it);
            if (nom && decodeURI(new File(nom).name).toLowerCase() === String(p.name).toLowerCase()) { it.file = f; ids.push(it.uuid); }
        }
        return {n: ids.length, ids: ids};
    }};
    T['preview'] = {req: ['path'], run: function (p) {
        var c = C(), a = planche(p.artboard), f = fichier(p.path, false), o = new ImageCaptureOptions();
        o.resolution = p.dpi || 72; o.antiAliasing = true;
        c.d.imageCapture(f, c.pl[a], o);
        return {path: f.fsName};
    }};
    // Sortie par plan de travail, sans changer le document ouvert (Exporter pour les écrans).
    T['export'] = {req: ['dir', 'format'], run: function (p) {
        var c = C(), d = c.d, dos = new Folder(String(p.dir)), fmt = String(p.format).toLowerCase(), o, type, e, avant = {}, l, i, files = [];
        var cle = 'plugin/SmartExportUI/CreateFoldersPreference', sous = app.preferences.getBooleanPreference(cle);
        if (!dos.exists && !dos.create()) throw erreur('dossier', 'Dossier impossible à créer : ' + dos.fsName);
        if (fmt === 'pdf') { o = new ExportForScreensPDFOptions(); if (p.preset) o.pdfPreset = String(p.preset); type = ExportForScreensType.SE_PDF; }
        else if (fmt === 'png') { o = new ExportForScreensOptionsPNG24(); o.scaleType = ExportForScreensScaleType.SCALEBYRESOLUTION; o.scaleTypeValue = p.dpi || 150; type = ExportForScreensType.SE_PNG24; }
        else if (fmt === 'jpg') { o = new ExportForScreensOptionsJPEG(); o.scaleType = ExportForScreensScaleType.SCALEBYRESOLUTION; o.scaleTypeValue = p.dpi || 150; type = ExportForScreensType.SE_JPEG100; }
        else if (fmt === 'svg') { o = new ExportForScreensOptionsWebOptimizedSVG(); type = ExportForScreensType.SE_SVG; }
        else throw erreur('parametres', 'format : pdf, png, jpg ou svg');
        e = new ExportForScreensItemToExport(); e.document = false;
        e.artboards = p.artboards ? String(p.artboards) : '1-' + c.pl.length;
        l = dos.getFiles(); for (i = 0; i < l.length; i++) avant[l[i].name] = l[i].modified ? l[i].modified.getTime() : 0;
        app.preferences.setBooleanPreference(cle, false);
        try { d.exportForScreens(dos, type, o, e, p.prefix ? String(p.prefix) : ''); }
        finally { app.preferences.setBooleanPreference(cle, sous); }
        l = dos.getFiles();
        for (i = 0; i < l.length; i++) if (l[i] instanceof File && (avant[l[i].name] === undefined || avant[l[i].name] !== l[i].modified.getTime())) files.push(decodeURI(l[i].name));
        return {dir: dos.fsName, files: files};
    }};
    T['save_document'] = {req: [], run: function (p) {
        var d = C().d, f, ext, o;
        if (p.path === undefined || p.path === null) {
            if (!String(d.path)) throw erreur('parametres', 'Document jamais enregistré : donnez path');
            d.save(); return {path: d.fullName.fsName};
        }
        f = fichier(p.path, false); ext = f.name.replace(/^.*\./, '').toLowerCase();
        if (ext === 'ai') o = new IllustratorSaveOptions();
        else if (ext === 'pdf') { o = new PDFSaveOptions(); if (p.preset) o.pDFPreset = String(p.preset); }
        else throw erreur('parametres', 'save_document : .ai ou .pdf (le document ouvert devient ce fichier)');
        d.saveAs(f, o); ctx = null;
        return {path: app.activeDocument.fullName.fsName};
    }};
    T['menu'] = {req: ['command'], run: function (p) { app.executeMenuCommand(String(p.command)); }};
    T['undo'] = {req: [], seule: true, run: function (p) {
        var i, n = p.steps || 1;
        C();
        for (i = 0; i < n; i++) app.undo();
        return {steps: n};
    }};
    T['snapshot'] = {req: [], run: function (p) { return snapshot(p); }};

    // ---------------------------------------------------------------- moteur de lot
    // Remplace "$n.champ" par le champ du résultat de l'opération n.
    function resoudre(v, valeurs, dry) {
        var m, n, src, o, k, i;
        if (typeof v === 'string') {
            m = REF.exec(v);
            if (!m) return v;
            n = Number(m[1]); src = valeurs[n];
            if (src && src[m[2]] !== undefined) return src[m[2]];
            if (dry) return '<' + v + '>';
            throw erreur('reference', v + ' : l\'opération ' + n + ' n\'a pas rendu le champ ' + m[2]);
        }
        if (estTableau(v)) { o = []; for (i = 0; i < v.length; i++) o.push(resoudre(v[i], valeurs, dry)); return o; }
        if (v && typeof v === 'object') { o = {}; for (k in v) if (v.hasOwnProperty(k)) o[k] = resoudre(v[k], valeurs, dry); return o; }
        return v;
    }
    function lot(p) {
        var ops = p.operations || [], stop = p.stop_on_error !== false, dry = !!p.dry_run, sortie = [], valeurs = [], i, j, op, def, q, r;
        for (i = 0; i < ops.length; i++) {
            def = T[(ops[i] || {}).c];
            if (def && def.seule && ops.length > 1 && !dry) throw erreur('parametres', ops[i].c + ' doit être la seule opération de son lot : Illustrator annule seulement entre deux appels');
        }
        for (i = 0; i < ops.length; i++) {
            op = ops[i] || {};
            try {
                def = T[op.c];
                if (!def) throw erreur('commande_inconnue', 'commande inconnue : ' + op.c);
                q = resoudre(op.p || {}, valeurs, dry);
                for (j = 0; j < def.req.length; j++) if (q[def.req[j]] === undefined || q[def.req[j]] === null) throw erreur('parametres', op.c + ' : paramètre obligatoire absent : ' + def.req[j]);
                r = dry ? undefined : def.run(q);
                valeurs[i] = r || {};
                sortie.push(r === undefined || r === null ? {i: i, ok: true} : {i: i, ok: true, r: r});
            } catch (e) {
                valeurs[i] = null;
                sortie.push({i: i, ok: false, e: {code: e.code || 'erreur', message: String(e.message || e)}});
                if (stop) break;
            }
        }
        return sortie;
    }

    function script(p) {
        var r = (function () { return eval(arguments[0]); }).call($.global, String(p.code));
        if (r === undefined || r === null) return '';
        return typeof r === 'object' && !(r instanceof String) ? json(r) : String(r);
    }
    function etat() {
        var o = {moteur: VERSION, illustrator: app.version, documents: app.documents.length};
        if (app.documents.length) o.document = app.activeDocument.name;
        return o;
    }

    function appel(c, p) {
        var niveau = app.userInteractionLevel, repere = null, r;
        ctx = null; p = p || {};
        app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
        try {
            if (app.documents.length) { repere = app.coordinateSystem; app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM; }
            if (c === 'status') r = etat();
            else if (c === 'snapshot') r = snapshot(p);
            else if (c === 'batch') r = lot(p);
            else if (c === 'execute_script') r = script(p);
            else throw erreur('commande_inconnue', 'commande inconnue : ' + c);
            return json({ok: true, r: r});
        } catch (e) {
            return json({ok: false, e: {code: e.code || 'erreur', message: String(e.message || e) + (c === 'execute_script' && e.line ? ' (ligne ' + e.line + ')' : '')}});
        } finally {
            ctx = null;
            try { if (repere !== null && app.documents.length) app.coordinateSystem = repere; } catch (e2) {}
            app.userInteractionLevel = niveau;
        }
    }

    return {version: VERSION, appel: appel, json: json};
})();
