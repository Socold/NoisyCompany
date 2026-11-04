// NoisyCompany browser companion: background event page (Firefox MV3).
// Off by default. When on, and only while the user is active, it makes a rare visit to
// a decoy persona page from the real browser: same TLS stack and network signature as
// the user's own browsing, which the stdlib daemon cannot imitate.
"use strict";

const TICK_MIN = 5;
const CONTAINER_NAME = "NoisyCompany";

async function settings() {
  const s = await browser.storage.local.get("settings");
  return { ...NC.DEFAULTS, ...(s.settings || {}) };
}

async function state() {
  const s = await browser.storage.local.get(["usage", "frontiers", "salt", "log"]);
  if (!s.salt) {
    const b = new Uint8Array(16);
    crypto.getRandomValues(b);
    s.salt = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
    await browser.storage.local.set({ salt: s.salt });
  }
  return { usage: s.usage || {}, frontiers: s.frontiers || {}, salt: s.salt, log: s.log || [] };
}

async function containerId() {
  if (!browser.contextualIdentities) return undefined;
  const found = await browser.contextualIdentities.query({ name: CONTAINER_NAME });
  if (found.length) return found[0].cookieStoreId;
  const c = await browser.contextualIdentities.create(
    { name: CONTAINER_NAME, color: "toolbar", icon: "fence" });
  return c.cookieStoreId;
}

async function fetchCapped(url, maxBytes) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 10000);
  try {
    const r = await fetch(url, { credentials: "omit", referrerPolicy: "no-referrer",
                                 signal: ctrl.signal, redirect: "manual" });
    // A redirect is not followed: it could point outside the persona domains, or to a
    // LAN address (router, NAS) that the browser would happily request.
    const type = r.headers.get("content-type") || "";
    if (!r.ok || !type.includes("html")) { ctrl.abort(); return { kb: 6, html: "", ok: r.ok }; }
    const reader = r.body.getReader();
    const chunks = [];
    let n = 0;
    while (n < maxBytes) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      n += value.length;
    }
    ctrl.abort();  // stop downloading past the cap
    const html = new TextDecoder().decode(
      chunks.reduce((a, c) => { const m = new Uint8Array(a.length + c.length);
        m.set(a); m.set(c, a.length); return m; }, new Uint8Array()));
    return { kb: Math.ceil(n / 1024) + 6, html, ok: true };
  } catch {
    return { kb: 6, html: "", ok: false };
  } finally {
    clearTimeout(timer);
  }
}

// Opt-in: the daemon's dashboard decides on/off. Read-only GET, localhost only, short
// timeout; unreachable daemon = the popup setting applies.
async function daemonEnabled(s) {
  if (!s.daemonLink) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 2000);
  try {
    const r = await fetch(`http://127.0.0.1:${s.daemonPort}/api/status`,
      { credentials: "omit", redirect: "error", signal: ctrl.signal });
    return r.ok ? NC.daemonSwitch(await r.json()) : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function personaPool(s) {
  return NC.personaNames(NC_PERSONAS, s.locales);
}

async function openTab(url, s) {
  if (NC_CHROMIUM) return;  // no containers: never open a tab with the user's cookies
  const cookieStoreId = s.tabContainer === "default" ? undefined : await containerId();
  const tab = await browser.tabs.create({ url, active: false, ...(cookieStoreId ? { cookieStoreId } : {}) });
  await browser.tabs.update(tab.id, { muted: true });
  if (browser.tabs.hide) browser.tabs.hide(tab.id).catch(() => {});
  const [lo, hi] = s.tabLifetimeS;
  setTimeout(() => browser.tabs.remove(tab.id).catch(() => {}), (lo + Math.random() * (hi - lo)) * 1000);
}

async function visit(force = false) {
  const s = await settings();
  const linked = await daemonEnabled(s);
  const enabled = linked === null ? s.enabled : linked;
  if (!enabled && !force) return null;
  if (!force) {
    if ((await browser.idle.queryState(300)) !== "active") return null;
    if (Math.random() >= NC.actProbability(TICK_MIN, s.meanGapMin)) return null;
  }
  const st = await state();
  const day = NC.today();
  const tab = s.mode === "tab" && !NC_CHROMIUM;
  const cost = tab ? NC.TAB_COST_KB : s.maxResponseKB + 6;
  if (!NC.canSpend(st.usage, day, cost, s.dailyKB)) return null;

  const names = NC.activePersonas(personaPool(s), st.salt, s.rotateDays, s.activePersonas);
  const name = names[Math.floor(Math.random() * names.length)];
  const persona = NC_PERSONAS[name];
  const url = NC.nextUrl(persona, st.frontiers[name]);

  let kb = cost;
  let ok = true;
  if (tab) {
    await openTab(url, s);
  } else {
    const res = await fetchCapped(url, s.maxResponseKB * 1024);
    kb = res.kb;
    ok = res.ok;
    const links = NC.candidateLinks(NC.extractLinks(res.html, url), persona);
    st.frontiers[name] = NC.updateFrontier(st.frontiers[name], links);
  }
  const log = [{ t: Date.now(), persona: name, host: new URL(url).hostname, kb, ok, mode: s.mode },
               ...st.log].slice(0, 20);
  await browser.storage.local.set({ usage: NC.spend(st.usage, day, kb), frontiers: st.frontiers, log });
  return log[0];
}

browser.alarms.create("tick", { periodInMinutes: TICK_MIN });
browser.alarms.onAlarm.addListener((a) => { if (a.name === "tick") visit().catch(() => {}); });

async function handle(msg) {
  if (msg && msg.type === "status") {
    const [s, st] = [await settings(), await state()];
    const day = NC.today();
    return { settings: s, usage: st.usage.day === day ? st.usage : { day, kb: 0, visits: 0 },
             log: st.log, chromium: NC_CHROMIUM, daemon: await daemonEnabled(s),
             personas: NC.activePersonas(personaPool(s), st.salt, s.rotateDays, s.activePersonas) };
  }
  if (msg && msg.type === "save" && msg.settings && typeof msg.settings === "object") {
    const cur = NC.sanitizeSettings(await settings(), msg.settings, NC_CHROMIUM);
    await browser.storage.local.set({ settings: cur });
    return { ok: true };
  }
  if (msg && msg.type === "visitNow") return visit(true);
  return undefined;
}

// sendResponse + `return true` works on both Firefox and Chromium.
browser.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== browser.runtime.id) return false;  // only our own popup
  handle(msg).then(sendResponse, () => sendResponse(undefined));
  return true;
});
