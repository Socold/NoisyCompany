"use strict";
// Static accessibility checks of the popup (same rules as the daemon dashboard).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "../src/popup.html"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "../src/popup.css"), "utf8");

test("every control has an accessible name", () => {
  const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
  for (const m of html.matchAll(/<(select|input|button)\b([^>]*)>/g)) {
    const attrs = m[2];
    const named = /aria-label(ledby)?="/.test(attrs) || m[1] === "button" && !/role="switch"/.test(attrs);
    const inLabel = html.lastIndexOf("<label", m.index) > html.lastIndexOf("</label>", m.index);
    assert.ok(named || inLabel, `unnamed control: ${m[0]}`);
    for (const ref of attrs.matchAll(/aria-(?:labelledby|describedby)="([^"]+)"/g))
      assert.ok(ids.has(ref[1]), `dangling reference ${ref[1]}`);
  }
});

test("the switch is not wrapped in a label (its name would be On/Off)", () => {
  assert.doesNotMatch(html, /<label[^>]*>(?:(?!<\/label>)[\s\S])*role="switch"/);
});

test("status text is announced and focus is visible", () => {
  assert.match(html, /id="usage"[^>]*role="status"/);
  assert.match(css, /:focus-visible/);
  assert.match(html, /<html lang="en">/);
});
