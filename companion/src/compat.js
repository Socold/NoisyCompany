// Same code on Firefox (browser.*) and Chromium (chrome.*, promise-based in MV3).
"use strict";
globalThis.NC_CHROMIUM = typeof browser === "undefined";
if (globalThis.NC_CHROMIUM) globalThis.browser = chrome;
