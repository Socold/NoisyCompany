"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const NC = require("../src/lib.js");

const persona = { seeds: ["https://en.wikipedia.org/wiki/Chess"], domains: ["en.wikipedia.org", "lichess.org"] };

test("defaults are off and light", () => {
  assert.equal(NC.DEFAULTS.enabled, false);
  assert.equal(NC.DEFAULTS.mode, "fetch");
  assert.ok(NC.DEFAULTS.dailyKB <= 4096);
});

test("extractLinks resolves, dedupes and drops anchors and non-http", () => {
  const html = '<a href="/wiki/Rook">r</a><A HREF=\'/wiki/Rook#x\'>r</A><a href="#top">t</a>'
    + '<a class="x" href="mailto:a@b">m</a><a href="https://lichess.org/learn?a=1&amp;b=2">l</a>';
  const links = NC.extractLinks(html, "https://en.wikipedia.org/wiki/Chess");
  assert.deepEqual(links, ["https://en.wikipedia.org/wiki/Rook", "https://lichess.org/learn?a=1&b=2"]);
});

test("candidateLinks keeps persona domains only, https only, no blocked URL", () => {
  const out = NC.candidateLinks([
    "https://en.wikipedia.org/wiki/Rook", "http://en.wikipedia.org/wiki/Pawn",
    "https://evil-wikipedia.org/x", "https://lichess.org/login", "https://ads.example/aclk",
  ], persona);
  assert.deepEqual(out, ["https://en.wikipedia.org/wiki/Rook"]);
});

test("budget: cannot exceed the daily cap, resets next day", () => {
  let u = {};
  u = NC.spend(u, "2026-08-10", 1900);
  assert.equal(NC.canSpend(u, "2026-08-10", 200, 2048), false);
  assert.equal(NC.canSpend(u, "2026-08-11", 200, 2048), true);
  assert.equal(NC.spend(u, "2026-08-11", 10).kb, 10);
});

test("persona rotation is stable within a period and salted", () => {
  const names = ["a", "b", "c", "d", "e", "f"];
  const t = Date.UTC(2026, 7, 10);
  const a = NC.activePersonas(names, "salt1", 10, 3, t);
  assert.equal(a.length, 3);
  assert.deepEqual(NC.activePersonas(names, "salt1", 10, 3, t + 3600e3), a);
  const others = ["s2", "s3", "s4", "s5", "s6"].map((s) => NC.activePersonas(names, s, 10, 3, t).join());
  assert.ok(others.some((o) => o !== a.join()));
});

test("act probability averages one visit per mean gap", () => {
  assert.equal(NC.actProbability(5, 25), 0.2);
  assert.equal(NC.actProbability(5, 1), 1);
});

test("nextUrl stays on persona domains and frontier is bounded", () => {
  const f = NC.updateFrontier([], Array.from({ length: 50 }, (_, i) => `https://en.wikipedia.org/wiki/P${i}`), 20);
  assert.equal(f.length, 20);
  for (let i = 0; i < 50; i++) assert.ok(NC.hostAllowed(NC.nextUrl(persona, [...f, "https://evil.example/"]), persona.domains));
});
