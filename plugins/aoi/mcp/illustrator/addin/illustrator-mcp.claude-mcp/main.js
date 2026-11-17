// Panneau « Claude MCP » (CEP) : connexion WebSocket au serveur MCP, sur demande seulement.
// Le panneau transmet chaque commande au moteur ExtendScript (moteur.jsx) par evalScript.
// Il ne reçoit jamais de code du serveur, sauf pour execute_script quand la case du panneau est cochée.
"use strict";

const VERSION = "0.1.0";
const URLS = ["ws://127.0.0.1:8766", "ws://localhost:8766"];
const COMMANDES = ["status", "snapshot", "batch", "execute_script"];
const CHARGER = "\u0001charger";

const adobe = window.__adobe_cep__ || null;   // absent hors d'Illustrator (navigateur)
let sock = null;
const fileLog = [];   // erreurs en attente d'envoi au serveur (20 au plus)

const $ = (s) => document.getElementById(s);

// Envoie une erreur JavaScript au serveur MCP : Claude la lit dans status.
function signaler(texte) {
  fileLog.push(String(texte).slice(0, 500));
  if (fileLog.length > 20) fileLog.shift();
  viderLog();
}

function viderLog() {
  while (fileLog.length && sock && sock.readyState === 1) sock.send(JSON.stringify({ log: fileLog.shift() }));
}

function texteErreur(e) {
  return String((e && e.stack) || (e && e.message) || e);
}

function faireErreur(code, message) {
  const e = new Error(message);
  e.code = code;
  return e;
}

window.addEventListener("error", (ev) => signaler("error : " + (ev.message || texteErreur(ev.error))));
window.addEventListener("unhandledrejection", (ev) => signaler("rejet : " + texteErreur(ev.reason)));

// ---- Illustrator : hôte, thème, moteur ExtendScript ----------------------------------------
function hote() {
  try { return JSON.parse(adobe.getHostEnvironment()); } catch (e) { return {}; }
}

function versionHote() {
  return String(hote().appVersion || "?");
}

// Reprend le fond du panneau d'Illustrator. Fond clair : couleurs de texte du thème clair.
function appliquerTheme() {
  let c = null;
  try { c = hote().appSkinInfo.panelBackgroundColor.color; } catch (e) { /* hors d'Illustrator */ }
  if (!c) return;
  const r = Math.round(c.red), v = Math.round(c.green), b = Math.round(c.blue);
  document.body.style.setProperty("--fond", "rgb(" + r + "," + v + "," + b + ")");
  document.body.className = (r * 299 + v * 587 + b * 114) / 1000 > 128 ? "clair" : "";
}

// Exécute un texte ExtendScript dans Illustrator. Rend le texte de la dernière valeur.
function evaluer(source) {
  return new Promise((resolve, reject) => {
    if (!adobe) { reject(faireErreur("canal", "panneau hors d'Illustrator")); return; }
    adobe.evalScript(source, (r) => {
      if (r === "EvalScript error.") reject(faireErreur("script", "erreur ExtendScript (evalScript)"));
      else resolve(String(r));
    });
  });
}

// Écrit une valeur en littéral JavaScript ASCII : sûr pour ExtendScript (U+2028, U+2029, accents).
function litteral(valeur) {
  return JSON.stringify(valeur).replace(/[\u007f-￿]/g, (c) => "\\u" + ("000" + c.charCodeAt(0).toString(16)).slice(-4));
}

function cheminExtension() {
  let p = String(adobe.getSystemPath("extension"));
  try { p = decodeURI(p); } catch (e) { /* chemin déjà décodé */ }
  return p.replace(/^file:\/{2,3}/, "");
}

// Charge moteur.jsx dans Illustrator. Le fichier est lu en UTF-8 par le panneau, puis envoyé comme texte.
let versionMoteur = null;

async function chargerMoteur() {
  const lu = window.cep.fs.readFile(cheminExtension() + "/moteur.jsx");
  if (lu.err) throw faireErreur("chargement", "moteur.jsx illisible (code " + lu.err + ")");
  const r = await evaluer(lu.data + "\n$.global.__aimcp ? $.global.__aimcp.version : '';");
  if (!r) throw faireErreur("chargement", "moteur.jsx chargé, mais __aimcp est absent");
  versionMoteur = r;
  afficherVersion();
}

// Appelle le moteur. Le moteur rend toujours un texte JSON {ok, r} ou {ok:false, e}.
async function appelMoteur(c, p) {
  const source = "(function(){var m=$.global.__aimcp;if(!m)return " + litteral(CHARGER) + ";return m.appel("
    + litteral(c) + "," + litteral(p) + ");})();";
  let brut = await evaluer(source);
  if (brut === CHARGER) {
    await chargerMoteur();
    brut = await evaluer(source);
  }
  let reponse;
  try { reponse = JSON.parse(brut); } catch (e) { throw faireErreur("canal", "réponse illisible du moteur : " + brut.slice(0, 200)); }
  if (!reponse.ok) throw faireErreur((reponse.e && reponse.e.code) || "erreur", (reponse.e && reponse.e.message) || "erreur du moteur");
  return reponse.r;
}

function lireReglage() {
  try { return localStorage.getItem("execute_script") === "1"; } catch (e) { return false; }
}

// ---- affichage du panneau ---------------------------------------------------------------
const ENTREES_MAX = 50;   // 5 lignes visibles, le reste défile
const compte = { ok: 0, ko: 0, ops: 0 };
const lignes = [];        // la plus récente en premier

function detail(texte) {
  $("detail").textContent = texte;
}

function bloc(classe, texte) {
  const e = document.createElement("div");
  e.className = classe;
  if (texte !== undefined) e.textContent = texte;
  return e;
}

function dessinerJournal() {
  const liste = $("journal");
  while (liste.firstChild) liste.removeChild(liste.firstChild);
  if (lignes.length === 0) liste.appendChild(bloc("vide", "Aucune commande reçue."));
  for (const l of lignes) {
    const ligne = bloc("entree " + l.genre);
    ligne.appendChild(bloc("heure", l.heure));
    ligne.appendChild(bloc("puce"));
    const t = bloc("texte", l.texte.slice(0, 160));
    t.title = l.texte.slice(0, 500);   // texte complet au survol
    ligne.appendChild(t);
    if (l.ms !== undefined) ligne.appendChild(bloc("duree", l.ms < 1000 ? l.ms + " ms" : (l.ms / 1000).toFixed(1) + " s"));
    liste.appendChild(ligne);
  }
  liste.scrollTop = 0;   // revient à la commande la plus récente
}

// Ajoute une ligne au journal du panneau. genre : "ok", "ko" ou "info". ms : durée de la commande.
function journal(texte, genre, ms) {
  lignes.unshift({ heure: new Date().toLocaleTimeString(), texte: String(texte), genre: genre || "info", ms });
  if (lignes.length > ENTREES_MAX) lignes.pop();
  dessinerJournal();
}

function compter(genre, operations) {
  compte[genre]++;
  compte.ops += operations;
  $("nb-ok").textContent = String(compte.ok);
  $("nb-ko").textContent = String(compte.ko);
  $("nb-ko").className = compte.ko ? "nombre actif" : "nombre";
  $("nb-ops").textContent = String(compte.ops);
}

function afficherReglage() {
  const actif = lireReglage();
  $("securite").className = actif ? "actif" : "";
  $("aide-script").textContent = actif
    ? "Claude peut exécuter du code libre dans Illustrator. Décochez hors besoin."
    : "Claude ne peut pas exécuter de code libre dans Illustrator.";
}

function afficherVersion() {
  $("version").textContent = "v" + VERSION + " · Illustrator " + versionHote().split(".").slice(0, 2).join(".")
    + (versionMoteur ? "" : " · moteur non chargé");
}

// La pastille clignote pendant un essai de connexion. Tout changement d'état arrête le clignotement.
let clignotement = null;

function clignoter(actif) {
  if (clignotement) { clearInterval(clignotement); clignotement = null; }
  $("voyant").className = "";
  if (!actif) return;
  clignotement = setInterval(() => {
    $("voyant").className = $("voyant").className ? "" : "eteinte";
  }, 600);
}

// consigne : texte sous l'état quand le panneau n'est pas connecté.
function etat(connecte, consigne) {
  clignoter(false);
  $("etat").textContent = connecte ? "Connecté à Claude" : "Déconnecté";
  $("tete").className = connecte ? "ok" : "ko";
  $("corps").className = connecte ? "" : "inactif";      // grisé hors connexion
  $("version").className = connecte ? "" : "inactif";
  $("bouton").textContent = connecte ? "Déconnecter" : "Connecter";   // suit la pastille : vert = Déconnecter
  if (!connecte) detail(consigne || "Cliquez sur Connecter.");
}

function envoyer(objet) {
  if (sock && sock.readyState === 1) sock.send(JSON.stringify(objet));
}

function bonjour() {
  envoyer({ hello: { version: VERSION, illustrator: versionHote(), moteur: versionMoteur, execute_script: lireReglage() } });
  viderLog();
}

async function repartir(c, p) {
  if (COMMANDES.indexOf(c) < 0) throw faireErreur("commande_inconnue", "commande inconnue : " + c);
  if (c === "execute_script" && !lireReglage()) {
    throw faireErreur("desactive", "execute_script désactivé : cochez « Autoriser les scripts ExtendScript (JSX) » dans le panneau Claude MCP");
  }
  return appelMoteur(c, p);
}

async function traiter(texte) {
  let m;
  try { m = JSON.parse(texte); } catch (e) { return; }
  let reponse;
  const debut = Date.now();
  const p = m.p || {};
  const ops = m.c === "batch" && Array.isArray(p.operations) ? p.operations.length : 1;
  const nom = m.c === "batch" ? "batch · " + ops + " op." + (p.dry_run ? " (à blanc)" : "") : String(m.c);
  try {
    reponse = { id: m.id, ok: true, r: await repartir(m.c, p) };
    const echecs = m.c === "batch" && Array.isArray(reponse.r) ? reponse.r.filter((x) => !x.ok) : [];
    if (echecs.length) {
      compter("ko", ops);
      journal(nom + " — op. " + echecs[0].i + " : " + echecs[0].e.message, "ko", Date.now() - debut);
    } else {
      compter("ok", ops);
      journal(nom, "ok", Date.now() - debut);
    }
  } catch (e) {
    reponse = { id: m.id, ok: false, e: { code: e.code || "erreur", message: String((e && e.message) || e) } };
    compter("ko", ops);
    journal(nom + " — " + reponse.e.message, "ko", Date.now() - debut);
    if (!e.code) signaler(m.c + " : " + texteErreur(e));   // erreur imprévue : la pile part au serveur
  }
  envoyer(reponse);
}

// Le panneau ne tente rien seul : ni au chargement, ni après une connexion perdue.
// Un clic sur « Connecter » fait un essai : 127.0.0.1, puis localhost si la première adresse échoue.
const DELAI_ESSAI_MS = 3000;
const SANS_SERVEUR = "Aucun serveur. Ouvrez une session Claude Code, puis cliquez sur Connecter.";

function connecter(rang) {
  const url = URLS[rang];
  let ouvert = false;
  let s;
  try {
    s = new WebSocket(url);
  } catch (e) {
    sock = null;
    etat(false, "WebSocket refusé (" + url + ") : " + ((e && e.message) || e));
    return;
  }
  sock = s;
  const suite = () => {   // l'essai sur cette adresse a échoué
    if (sock !== s) return;
    sock = null;
    if (rang + 1 < URLS.length) { connecter(rang + 1); return; }
    etat(false, SANS_SERVEUR);
  };
  // Sans réponse en 3 s, l'essai est abandonné : le panneau ne reste pas sur « Connexion… ».
  const limite = setTimeout(() => { if (!ouvert) { try { s.close(); } catch (e) { /* */ } suite(); } }, DELAI_ESSAI_MS);
  s.onopen = () => { ouvert = true; clearTimeout(limite); etat(true); bonjour(); detail(url.replace("ws://", "")); };
  s.onmessage = (ev) => traiter(ev.data);
  s.onerror = () => { /* onclose suit */ };
  s.onclose = () => {
    clearTimeout(limite);
    if (!ouvert) { suite(); return; }
    if (sock !== s) return;
    sock = null;
    etat(false, coupure ? "Cliquez sur Connecter." : "Connexion fermée par le serveur. Cliquez sur Connecter.");
  };
}

let coupure = false;   // vrai quand l'utilisateur a cliqué sur « Déconnecter »

$("bouton").addEventListener("click", () => {
  if (sock && sock.readyState === 1) { coupure = true; sock.close(); return; }
  if (sock) return;   // essai déjà en cours
  coupure = false;
  etat(false, "Connexion…");
  clignoter(true);
  connecter(0);
});

$("autoriser").checked = lireReglage();
$("autoriser").addEventListener("change", (ev) => {
  try { localStorage.setItem("execute_script", ev.target.checked ? "1" : "0"); } catch (e) { /* */ }
  afficherReglage();
  bonjour();
});

appliquerTheme();
try { adobe.addEventListener("com.adobe.csxs.events.ThemeColorChanged", appliquerTheme); } catch (e) { /* hors d'Illustrator */ }
dessinerJournal();
afficherReglage();
afficherVersion();
etat(false);   // aucun essai de connexion au chargement
// Le moteur est chargé dès l'ouverture du panneau : une erreur de syntaxe se voit tout de suite.
if (adobe) chargerMoteur().catch((e) => { signaler("chargement : " + texteErreur(e)); detail("Moteur non chargé : " + e.message); });
