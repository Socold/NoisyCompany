"use strict";
const $ = (id) => document.getElementById(id);
const HELP = {
  fetch: "Fetches persona pages in the background with your browser's network stack, "
       + "without cookies. Dilutes what your ISP and DNS resolver see. ~100 KB per visit.",
  tab: "Opens a hidden, muted tab in a separate 'NoisyCompany' container, closed after "
     + "~40 s. Trackers on that page build a decoy profile. Keeps your own cookies apart. "
     + "~2 MB per visit. Your content blocker still applies.",
};

const DEFAULT_CONTAINER_WARNING = "Tab visits will use your normal cookies. Sites and "
  + "trackers will add the decoy interests to YOUR profile: that is the point of this "
  + "option (it dilutes your real ad profile), but it also mixes their logins and history "
  + "with yours. Continue?";
const DAEMON_ORIGIN = "http://127.0.0.1/*";

async function load() {
  const s = await browser.runtime.sendMessage({ type: "status" });
  const on = s.daemon === null || s.daemon === undefined ? s.settings.enabled : s.daemon;
  $("enabled").setAttribute("aria-checked", String(on));
  $("enabled").textContent = on ? "On" : "Off";
  $("mode").value = s.settings.mode;
  $("mode").querySelector('option[value="tab"]').disabled = s.chromium;
  $("containerrow").hidden = s.chromium || s.settings.mode !== "tab";
  $("tabContainer").value = s.settings.tabContainer;
  $("tabContainer").classList.toggle("warn", s.settings.tabContainer === "default");
  for (const box of document.querySelectorAll(".locales input"))
    box.checked = s.settings.locales.includes(box.value);
  $("daemonLink").checked = s.settings.daemonLink;
  $("enabled").disabled = s.settings.daemonLink && s.daemon !== null;
  $("daemonhelp").textContent = !s.settings.daemonLink ? ""
    : s.daemon === null ? `Daemon not reachable on 127.0.0.1:${s.settings.daemonPort} (dashboard switch on?): the switch above applies.`
    : `Controlled by the daemon: browser_companion is ${s.daemon ? "on" : "off"}.`;
  $("modehelp").textContent = HELP[s.settings.mode];
  $("dailyKB").value = s.settings.dailyKB;
  $("meanGapMin").value = s.settings.meanGapMin;
  $("usage").textContent = `Today: ${s.usage.visits} visits, ${s.usage.kb} of ${s.settings.dailyKB} KB.`;
  $("personas").textContent = "Active personas: " + s.personas.join(", ");
  $("log").replaceChildren(...s.log.slice(0, 5).map((e) => {
    const li = document.createElement("li");
    li.textContent = `${new Date(e.t).toLocaleTimeString()} ${e.persona} ${e.host} ${e.kb} KB${e.ok ? "" : " (failed)"}`;
    return li;
  }));
}

async function save(patch) {
  await browser.runtime.sendMessage({ type: "save", settings: patch });
  await load();
}

$("enabled").addEventListener("click", () =>
  save({ enabled: $("enabled").getAttribute("aria-checked") !== "true" }));
$("mode").addEventListener("change", () => save({ mode: $("mode").value }));
$("dailyKB").addEventListener("change", () => save({ dailyKB: Number($("dailyKB").value) }));
$("meanGapMin").addEventListener("change", () => save({ meanGapMin: Number($("meanGapMin").value) }));
$("tabContainer").addEventListener("change", async () => {
  const v = $("tabContainer").value;
  if (v === "default" && !window.confirm(DEFAULT_CONTAINER_WARNING)) { await load(); return; }
  await save({ tabContainer: v });
});
for (const box of document.querySelectorAll(".locales input"))
  box.addEventListener("change", () => save({ locales: [...document.querySelectorAll(".locales input:checked")].map((b) => b.value) }));
$("daemonLink").addEventListener("change", async () => {
  let on = $("daemonLink").checked;
  // Localhost access is optional: asked only now, from the user's click.
  if (on) on = await browser.permissions.request({ origins: [DAEMON_ORIGIN] });
  else await browser.permissions.remove({ origins: [DAEMON_ORIGIN] });
  await save({ daemonLink: on });
});
$("now").addEventListener("click", async () => {
  $("now").disabled = true;
  $("now").setAttribute("aria-busy", "true");
  await browser.runtime.sendMessage({ type: "visitNow" });
  $("now").disabled = false;
  $("now").removeAttribute("aria-busy");
  await load();
});
load();
