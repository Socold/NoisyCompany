// Build both browser packages from src/ (no dependency): build/firefox and build/chromium.
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const src = path.join(root, "src");
const FIREFOX_ONLY = new Set(["manifest.chromium.json", "sw.js"]);
const CHROMIUM_ONLY = new Set(["manifest.chromium.json"]);

for (const target of ["firefox", "chromium"]) {
  const out = path.join(root, "build", target);
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  for (const f of fs.readdirSync(src)) {
    if (target === "firefox" && FIREFOX_ONLY.has(f)) continue;
    if (target === "chromium" && (f === "manifest.json")) continue;
    const dest = target === "chromium" && CHROMIUM_ONLY.has(f) ? "manifest.json" : f;
    fs.copyFileSync(path.join(src, f), path.join(out, dest));
  }
  console.log(`build/${target}`);
}
