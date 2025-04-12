# Opportunities: roadmap, use cases, product ideas

## Roadmap

Every opportunity below is tracked in [ROADMAP.md](ROADMAP.md) with an on/off switch
(`noisycompany features`, or the dashboard buttons).

## Use cases

- **Home privacy box**: Raspberry Pi / router / NAS running NoisyCompany for the whole household.
- **Pi-hole / AdGuard Home add-on**: block + noise in the same box; DNS noise is the
  cheapest and best-blending kind.
- **Public Wi-Fi hygiene** on laptops (eco preset, only while on untrusted networks).
- **Teaching and awareness**: `noisycompany estimate` + threat model are a ready-made workshop on
  what an ISP sees and what really protects you.
- **Security labs**: realistic benign background traffic to test IDS/NDR rules, SOC
  detections (DNS anomaly, beaconing detection must not flag it) and SIEM pipelines.
- **Research**: reproducible benign traffic generator for traffic-classification and
  website-fingerprinting experiments.
- **Honeypot / canary realism**: a decoy machine that "lives" (a host with no traffic is
  suspicious to an intruder).

## Product ideas

- **Packaged appliance image** (Raspberry Pi, OpenWrt package, Home Assistant add-on,
  Umbrel/CasaOS app, TrueNAS app): one-click install, the main adoption lever.
- **Privacy score dashboard**: combine local checks (encrypted DNS on? ECH? blocker?) with
  noise stats into a household privacy report. Noise becomes one line of a broader tool.
- **B2B: benign traffic generator for SOC testing**, with labelled output (ground truth),
  personas per business profile, rate profiles. Clear market: detection engineering
  teams need realistic negatives.
- **Persona API for researchers** (dataset of realistic interest-coherent browsing).
- **Collective noise**: households sharing persona sets so that decoy profiles are
  indistinguishable across users (k-anonymity of interests). Needs careful design to
  avoid a central point that could be subpoenaed.

## Ideas rejected on purpose

- Clicking ads (AdNauseam-style): click fraud risk, harms publishers, banned from stores.
- Search-engine query injection at scale: violates ToS, triggers CAPTCHAs, and research
  shows it is filterable. Possible later as an opt-in, very low rate, in-browser feature.
- Sensitive or illegal content as decoys: may hurt the user.
- Headless full browsers by default: 10-100x the energy and bandwidth.
