"use strict";
const $ = (id) => document.getElementById(id);
const HELP = {
  fetch: "Fetches persona pages in the background with your browser's network stack, "
       + "without cookies. Dilutes what your ISP and DNS resolver see. ~100 KB per visit.",
  tab: "Opens a hidden, muted tab in a separate 'NoisyCompany' container, closed after "
     + "~40 s. Trackers on that page build a decoy profile. Keeps your own cookies apart. "
     + "~2 MB per visit. Your content blocker still applies.",
};

async function load() {
  const s = await browser.runtime.sendMessage({ type: "status" });
  const on = s.settings.enabled;
  $("enabled").setAttribute("aria-checked", String(on));
  $("enabled").textContent = on ? "On" : "Off";
  $("mode").value = s.settings.mode;
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
$("now").addEventListener("click", async () => {
  $("now").disabled = true;
  await browser.runtime.sendMessage({ type: "visitNow" });
  $("now").disabled = false;
  await load();
});
load();
