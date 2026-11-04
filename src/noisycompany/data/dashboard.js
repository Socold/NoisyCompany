"use strict";
const token = document.querySelector('meta[name="nc-token"]').content;
const $ = (id) => document.getElementById(id);
const mb = (b) => (b / 1e6).toFixed(b < 1e7 ? 2 : 1) + " MB";

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
    alert("Could not switch " + id + ": " + e.message);
  }
  await refresh();
}

function renderFeatures(list) {
  const ul = $("features");
  ul.replaceChildren();
  for (const f of list) {
    const li = el("li");
    const txt = el("div", { class: "txt" });
    const t = el("div", { class: "t" }, f.title);
    t.append(el("span", { class: "tag" }, f.available ? f.milestone : "planned " + f.milestone));
    txt.append(t, el("div", { class: "d" }, f.description));
    const btn = el("button", { class: "sw", role: "switch", "aria-checked": String(f.enabled),
                               "aria-label": f.title }, f.enabled ? "On" : "Off");
    if (!f.available) { btn.disabled = true; btn.title = "Not available yet"; }
    else if (f.id === "dashboard") { btn.disabled = true; btn.title = "Switch off from the CLI"; }
    btn.addEventListener("click", () => toggle(f.id, !f.enabled, btn));
    li.append(txt, btn);
    ul.append(li);
  }
}

async function refresh() {
  let s;
  try { s = await (await fetch("/api/status")).json(); }
  catch { $("state").textContent = "NoisyCompany is not responding."; return; }
  const pct = Math.min(100, (100 * s.bytes_today) / s.daily_cap_bytes);
  $("fill").style.width = pct + "%";
  $("meter").setAttribute("aria-valuenow", pct.toFixed(0));
  $("budget").textContent = mb(s.bytes_today) + " of " + mb(s.daily_cap_bytes) + " daily budget"
    + (s.metered ? " (metered connection: eco budget)" : "");
  const k = [["Sessions", s.stats.sessions], ["Pages", s.stats.pages_ok],
             ["DNS lookups", s.stats.dns_ok], ["Back-offs", s.stats.paused_busy],
             ["Since start", mb(s.stats.bytes)]];
  $("kpis").replaceChildren(...k.map(([a, b]) => {
    const d = el("div"); d.append(el("dt", {}, a), el("dd", {}, String(b))); return d;
  }));
  $("state").textContent = s.state;
  $("personas").replaceChildren(...s.active_personas.map((p) => el("li", {}, p)));
  renderFeatures(s.features);
  renderPrivacy(s.privacy);
}

function renderPrivacy(p) {
  const card = $("privacy-card");
  card.hidden = !p;
  if (!p) return;
  $("pscore").textContent = p.score === null ? "n/a" : p.score + "/100";
  const label = { pass: "OK", fail: "TO DO", unknown: "unknown" };
  $("privacy").replaceChildren(...p.checks.map((c) => {
    const li = el("li");
    li.append(el("span", { class: "st " + c.status }, label[c.status]),
              document.createTextNode(c.title + (c.detail ? " (" + c.detail + ")" : "")));
    if (c.status === "fail") li.append(el("div", { class: "adv" }, c.advice));
    return li;
  }));
}

refresh();
setInterval(refresh, 10000);
