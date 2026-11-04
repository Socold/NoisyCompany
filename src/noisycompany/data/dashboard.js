"use strict";
const token = document.querySelector('meta[name="nc-token"]').content;
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- i18n (en, fr)
const FR = {
  skip: "Aller aux interrupteurs", sub: "Tableau de bord local. Accessible depuis cette machine uniquement.",
  today: "Aujourd'hui", personas: "Personas leurres actives", privacy: "Rapport de confidentialité",
  privacySub: "Vérifications locales, rien n'est envoyé. Mis à jour toutes les 10 minutes.",
  features: "Fonctions", featuresSub: "Les interrupteurs s'appliquent à la session suivante, sans redémarrage.",
  of: "sur", budget: "de budget quotidien", metered: " (connexion limitée : budget éco)",
  Sessions: "Sessions", Pages: "Pages", "DNS lookups": "Requêtes DNS", "Back-offs": "Pauses",
  "Since start": "Depuis le démarrage", On: "Oui", Off: "Non", planned: "prévu",
  notResponding: "NoisyCompany ne répond pas.", couldNot: "Impossible de basculer",
  notAvailable: "Pas encore disponible", cliOnly: "À couper depuis la ligne de commande",
  OK: "OK", "TO DO": "À FAIRE", unknown: "inconnu",
  "running": "en marche", "outside active hours": "hors des heures actives",
  "paused: your own traffic is high": "en pause : votre trafic est élevé",
  "waiting: budget pacing": "en attente : étalement du budget", "starting": "démarrage",
  "stopped": "arrêté",
};
// Feature titles and descriptions; a feature missing here keeps its English text.
const FR_FEATURES = {
  persona_drift: ["Dérive des personas", "Un loisir principal reste des mois ; les intérêts secondaires changent tous les quelques jours."],
  locale_packs: ["Personas dans votre langue", "Ajoute des personas en français, allemand, espagnol ou italien pour que les leurres correspondent à votre langue."],
  metered_guard: ["Garde connexion limitée", "Sur une connexion limitée (NetworkManager), passe automatiquement au budget éco."],
  doh_sink: ["Bruit DNS en DoH", "Envoie le bruit DNS au même résolveur DNS-over-HTTPS que votre navigateur."],
  metrics: ["Métriques Prometheus", "Compteurs sur http://127.0.0.1:9789/metrics pour les tableaux de bord du labo maison."],
  dashboard: ["Tableau de bord local", "Cette page, sur http://127.0.0.1:9788, avec les statistiques et un interrupteur par fonction."],
  labelled_log: ["Journal étiqueté", "Écrit chaque action générée dans un fichier JSONL : du trafic bénin avec vérité terrain pour tester un SOC, un IDS ou un NDR."],
  privacy_report: ["Rapport de confidentialité", "Vérifications locales (bloqueur, DNS chiffré, anti-empreinte, GPC, IPv6, cohérence du bruit) réunies en un score. Rien n'est envoyé."],
  browser_companion: ["Extension navigateur", "Extension Firefox ou Chromium (companion/) : rares visites de leurres depuis le vrai navigateur. Elle peut suivre cet interrupteur."],
  persona_marketplace: ["Packs de personas", "Packs relus livrés avec le code, installables par nom (`noisycompany packs`), vérifiés en CI contre les sujets sensibles."],
  business_profiles: ["Profils métier", "Remplace les personas par un profil d'entreprise (bureau, équipe de dev, commerce) pour les labos SOC."],
  appliance_packages: ["Paquets boîtiers", "Add-on Home Assistant, docker-compose, Raspberry Pi, OpenWrt, Umbrel, CasaOS, TrueNAS, Unraid. Écrit un fichier de santé."],
  request_trees: ["Arbres de requêtes", "Charge aussi jusqu'à 3 CSS/JS du même site par page, une seule fois comme un cache. Environ +60 % de données."],
  collective_noise: ["Bruit collectif", "Rejoindre un collectif par code : les membres font tourner les mêmes personas au même moment. Sans serveur, sans nouveau domaine."],
  dns_coherence: ["DNS qui suit la lecture", "Le bruit DNS interroge les sites que la persona a lus et les liens vus, comme un navigateur qui y revient."],
  weekly_rhythm: ["Rythme de la semaine", "Plus actif le soir, matins plus tardifs le week-end et les jours fériés, plus calme l'été. Ne change jamais le plafond quotidien."],
  page_load_bursts: ["Rafales de chargement de page", "Rafales tierces de la taille d'un vrai chargement : 5 à 25 domaines en une seconde environ (domaines intégrés d'abord, puis ceux déjà lus par la persona). DNS seulement."],
  interleave_with_user: ["Mêlé à votre navigation", "Lance les sessions surtout quand vous êtes en ligne (compteur de trafic local), rarement quand le réseau est calme : bruit et vrai trafic partagent les mêmes heures."],
  third_party_bursts: ["Rafales de domaines tiers", "Après une page, résout (DNS seulement) quelques domaines tiers qu'elle charge. Publicité et traqueurs exclus. ~300 o chacun."],
  separability_study: ["Étude de détectabilité", "`noisycompany study` : mesure (AUC) si un observateur sépare le bruit de votre vrai trafic (Pi-hole, AdGuard...)."],
};
const FR_CHECKS = {
  blocker: ["Bloqueur de contenu dans le navigateur", "Installez uBlock Origin : il coupe la plupart du pistage publicitaire à la source."],
  encrypted_dns: ["DNS chiffré (DoH/DoT)", "Activez le DNS over HTTPS dans le navigateur (Firefox : Paramètres > Vie privée > DNS via HTTPS, protection maximale) ou DNSOverTLS dans systemd-resolved."],
  fingerprinting: ["Protection contre l'empreinte", "Firefox : protection renforcée « Stricte », ou Mullvad / Tor Browser."],
  gpc: ["Signal Global Privacy Control", "Firefox : privacy.globalprivacycontrol.enabled = true (signal légal de refus dans plusieurs pays)."],
  ipv6_privacy: ["Adresses IPv6 temporaires", "Réglez net.ipv6.conf.all.use_tempaddr = 2 pour que votre adresse IPv6 n'identifie pas l'appareil dans le temps."],
  noise: ["NoisyCompany en marche", "Lancez `noisycompany run` (ou le service systemd) pour diluer les profils vus du réseau."],
  noise_dns_coherence: ["Le bruit DNS va où va le DNS du navigateur", "Le navigateur utilise DoH : activez `doh_sink` avec le même résolveur, sinon le bruit DNS se sépare facilement."],
};

const wanted = new URLSearchParams(location.search).get("lang")
  || (navigator.language || "en").slice(0, 2);
const LANG = wanted === "fr" ? "fr" : "en";
const t = (s) => (LANG === "fr" && FR[s]) || s;
document.documentElement.lang = LANG;
for (const n of document.querySelectorAll("[data-i18n]")) {
  const k = n.dataset.i18n;
  if (LANG === "fr" && FR[k]) n.textContent = FR[k];
}
const mb = (b) => (b / 1e6).toLocaleString(LANG, { maximumFractionDigits: b < 1e7 ? 2 : 1 }) + " MB";

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}

async function toggle(id, on, btn) {
  btn.disabled = true;
  try {
    const r = await fetch("/api/features/" + encodeURIComponent(id), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-NC-Token": token },
      body: JSON.stringify({ on }),
    });
    if (!r.ok) throw new Error((await r.json()).error || r.status);
  } catch (e) {
    $("error").textContent = t("couldNot") + " " + id + " : " + e.message;
  }
  await refresh();
}

function renderFeatures(list) {
  const ul = $("features");
  // Update in place when the list is unchanged, so the 10 s refresh never steals the
  // keyboard focus from a switch.
  const ids = [...ul.children].map((li) => li.dataset.id).join();
  if (ids === list.map((f) => f.id).join()) {
    for (const f of list) {
      const btn = ul.querySelector(`li[data-id="${f.id}"] button`);
      btn.setAttribute("aria-checked", String(f.enabled));
      btn.textContent = t(f.enabled ? "On" : "Off");
      btn.onclick = () => toggle(f.id, !f.enabled, btn);
      if (f.available && f.id !== "dashboard") btn.disabled = false;
    }
    return;
  }
  ul.replaceChildren();
  for (const f of list) {
    const li = el("li", { "data-id": f.id });
    const txt = el("div", { class: "txt" });
    const fr = LANG === "fr" ? FR_FEATURES[f.id] : null;
    const title = fr ? fr[0] : f.title;
    const head = el("div", { class: "t", id: "f-" + f.id }, title);
    head.append(el("span", { class: "tag" }, f.available ? f.milestone : t("planned") + " " + f.milestone));
    txt.append(head, el("div", { class: "d", id: "d-" + f.id }, fr ? fr[1] : f.description));
    const btn = el("button", { class: "sw", role: "switch", "aria-checked": String(f.enabled),
                               "aria-labelledby": "f-" + f.id, "aria-describedby": "d-" + f.id },
                   t(f.enabled ? "On" : "Off"));
    if (!f.available) { btn.disabled = true; btn.title = t("notAvailable"); }
    else if (f.id === "dashboard") { btn.disabled = true; btn.title = t("cliOnly"); }
    btn.onclick = () => toggle(f.id, !f.enabled, btn);
    li.append(txt, btn);
    ul.append(li);
  }
}

async function refresh() {
  let s;
  try { s = await (await fetch("/api/status")).json(); }
  catch { $("error").textContent = t("notResponding"); return; }
  $("error").textContent = "";
  const pct = Math.min(100, (100 * s.bytes_today) / s.daily_cap_bytes);
  $("fill").style.width = pct + "%";
  $("meter").setAttribute("aria-valuenow", pct.toFixed(0));
  $("meter").setAttribute("aria-valuetext", mb(s.bytes_today) + " / " + mb(s.daily_cap_bytes));
  const EN = { budget: "daily budget", metered: " (metered connection: eco budget)" };
  const tr = (k) => (LANG === "fr" ? FR[k] : EN[k]);
  $("budget").textContent = mb(s.bytes_today) + " " + (LANG === "fr" ? "sur" : "of") + " " + mb(s.daily_cap_bytes) + " "
    + tr("budget") + (s.metered ? tr("metered") : "");
  const k = [["Sessions", s.stats.sessions], ["Pages", s.stats.pages_ok],
             ["DNS lookups", s.stats.dns_ok], ["Back-offs", s.stats.paused_busy],
             ["Since start", mb(s.stats.bytes)]];
  $("kpis").replaceChildren(...k.map(([a, b]) => {
    const d = el("div");
    d.append(el("dt", {}, t(a)), el("dd", {}, typeof b === "number" ? b.toLocaleString(LANG) : b));
    return d;
  }));
  $("state").textContent = t(s.state);
  $("personas").replaceChildren(...s.active_personas.map((p) => el("li", {}, p)));
  renderFeatures(s.features);
  renderPrivacy(s.privacy);
}

function renderPrivacy(p) {
  const card = $("privacy-card");
  card.hidden = !p;
  if (!p) return;
  $("pscore").textContent = p.score === null ? "n/a" : p.score + "/100";
  const label = { pass: t("OK"), fail: t("TO DO"), unknown: t("unknown") };
  const fr = (c) => (LANG === "fr" && FR_CHECKS[c.id]) || [];
  $("privacy").replaceChildren(...p.checks.map((c) => {
    const li = el("li");
    li.append(el("span", { class: "st " + c.status }, label[c.status]),
              document.createTextNode((fr(c)[0] || c.title) + (c.detail ? " (" + c.detail + ")" : "")));
    if (c.status === "fail") li.append(el("div", { class: "adv" }, fr(c)[1] || c.advice));
    return li;
  }));
}

refresh();
setInterval(refresh, 10000);
