// Pure logic of the NoisyCompany browser companion. No browser API here, so it is
// testable with `node --test`. Loaded as a classic script in the extension and as a
// CommonJS module in tests.
"use strict";

const BLOCKED = [
  "doubleclick", "googlesyndication", "adservice", "/ads", "adclick", "/aclk",
  "login", "signin", "signup", "logout", "account", "cart", "checkout", "payment",
  "donate", "subscribe", "mailto:", "javascript:", "tel:",
  ".pdf", ".zip", ".exe", ".dmg", ".iso", ".mp4", ".mp3", ".webm", ".jpg", ".png", ".gif",
];

const DEFAULTS = Object.freeze({
  enabled: false,
  mode: "fetch",          // "fetch": background request, no cookie, ~100 KB
                          // "tab": inactive muted tab in a dedicated container, ~2 MB
  dailyKB: 2048,          // hard daily cap (fetch mode ~ 15-20 visits)
  meanGapMin: 25,         // mean minutes between two visits while the user is active
  maxResponseKB: 192,
  tabLifetimeS: [20, 60],
  activePersonas: 3,
  rotateDays: 10,
  locales: ["en", "fr"],  // persona packs used (en = built-in)
  tabContainer: "noisycompany",  // or "default": your own cookies, opt-in with a warning
  daemonLink: false,      // follow the daemon's browser_companion switch (localhost)
  daemonPort: 9788,
});

const LOCALES = ["en", "fr", "de", "es", "it"];

function personaNames(personas, locales) {
  const want = new Set(locales && locales.length ? locales : ["en"]);
  return Object.keys(personas).filter((n) => want.has(personas[n].locale || "en"));
}

// Clean a settings patch coming from the popup. isChromium: no containers there, so no
// tab mode at all (a tab would carry the user's own cookies).
function sanitizeSettings(cur, patch, isChromium = false) {
  const out = { ...cur };
  for (const k of ["enabled", "mode", "dailyKB", "meanGapMin", "locales", "tabContainer",
                   "daemonLink", "daemonPort"]) if (patch && k in patch) out[k] = patch[k];
  out.enabled = out.enabled === true;
  out.mode = out.mode === "tab" && !isChromium ? "tab" : "fetch";
  out.dailyKB = Math.max(256, Math.min(20480, Number(out.dailyKB) || DEFAULTS.dailyKB));
  out.meanGapMin = Math.max(5, Math.min(240, Number(out.meanGapMin) || DEFAULTS.meanGapMin));
  out.locales = Array.isArray(out.locales) ? out.locales.filter((l) => LOCALES.includes(l)) : [];
  if (!out.locales.length) out.locales = ["en"];
  out.tabContainer = out.tabContainer === "default" ? "default" : "noisycompany";
  out.daemonLink = out.daemonLink === true;
  const port = Number(out.daemonPort);
  out.daemonPort = Number.isInteger(port) && port >= 1024 && port <= 65535 ? port : 9788;
  return out;
}

// Daemon dashboard /api/status -> true/false for its browser_companion switch, or null
// when the answer is not a NoisyCompany status (then the popup setting applies).
function daemonSwitch(status) {
  if (!status || !Array.isArray(status.features)) return null;
  const f = status.features.find((x) => x && x.id === "browser_companion");
  return f ? f.enabled === true : null;
}

const TAB_COST_KB = 2048;

function hostOf(url) {
  try { return new URL(url).hostname.toLowerCase(); } catch { return ""; }
}

function hostAllowed(url, domains) {
  const h = hostOf(url);
  return h !== "" && domains.some((d) => h === d || h.endsWith("." + d));
}

function isBlocked(url) {
  const low = url.toLowerCase();
  return BLOCKED.some((f) => low.includes(f));
}

// Regex-based on purpose: same code path in the extension and in node tests, and we
// never need more than href values. Truncated HTML is fine.
function extractLinks(html, baseUrl) {
  const out = new Set();
  const re = /<a\b[^>]*?\bhref\s*=\s*(["'])(.*?)\1/gis;
  let m;
  while ((m = re.exec(html)) !== null) {
    const raw = m[2].trim();
    if (!raw || raw.startsWith("#")) continue;
    try {
      const u = new URL(raw.replace(/&amp;/g, "&"), baseUrl);
      if (u.protocol !== "https:" && u.protocol !== "http:") continue;
      u.hash = "";
      out.add(u.toString());
    } catch { /* ignore malformed */ }
  }
  return [...out];
}

function candidateLinks(links, persona) {
  return links.filter((l) => l.startsWith("https://") && !isBlocked(l)
    && hostAllowed(l, persona.domains));
}

function today(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

// Deterministic PRNG (mulberry32) for the salted persona rotation.
function prng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h;
}

function activePersonas(names, salt, rotateDays, count, nowMs = Date.now()) {
  const epoch = Math.floor(nowMs / (rotateDays * 86400000));
  const rnd = prng(hashString(`${salt}:${epoch}`));
  const pool = [...names].sort();
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, Math.min(count, pool.length));
}

// Probability to act on one alarm tick so that visits average one per meanGapMin.
function actProbability(tickMin, meanGapMin) {
  return Math.min(1, tickMin / Math.max(meanGapMin, tickMin));
}

function canSpend(usage, day, costKB, dailyKB) {
  const used = usage.day === day ? usage.kb : 0;
  return used + costKB <= dailyKB;
}

function spend(usage, day, kb) {
  const base = usage.day === day ? usage : { day, kb: 0, visits: 0 };
  return { day, kb: base.kb + kb, visits: base.visits + 1 };
}

// Next URL for a persona: continue from its small frontier (links seen before) or
// start again from a seed. Keeps visits topical, like a person following links.
function nextUrl(persona, frontier, rnd = Math.random) {
  const pool = (frontier || []).filter((u) => hostAllowed(u, persona.domains) && !isBlocked(u));
  if (pool.length && rnd() < 0.6) return pool[Math.floor(rnd() * pool.length)];
  return persona.seeds[Math.floor(rnd() * persona.seeds.length)];
}

function updateFrontier(frontier, links, max = 20, rnd = Math.random) {
  const merged = [...new Set([...(frontier || []), ...links])];
  while (merged.length > max) merged.splice(Math.floor(rnd() * merged.length), 1);
  return merged;
}

const api = {
  BLOCKED, DEFAULTS, TAB_COST_KB, hostAllowed, isBlocked, extractLinks, candidateLinks,
  today, activePersonas, actProbability, canSpend, spend, nextUrl, updateFrontier,
  hashString, LOCALES, personaNames, sanitizeSettings, daemonSwitch,
};
if (typeof module !== "undefined") module.exports = api;
else globalThis.NC = api;
