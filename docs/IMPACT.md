# Impact: bandwidth, browsing, ecology

All figures can be reproduced with `noisycompany estimate [-p preset] [--grid gCO2/kWh]`.

## Bandwidth

| Preset | Data/day | Data/month | Mean rate when active | HD video equivalent/day |
|---|---|---|---|---|
| eco | ~2.3 MB | ~70 MB | ~0.3 kbit/s | ~3 s |
| balanced (default) | ~15 MB | ~450 MB | ~2.2 kbit/s | ~18 s |
| max | ~60 MB | ~1.8 GB | ~9 kbit/s | ~72 s |

For scale: a 4G/fibre connection carries 10 000 to 1 000 000 kbit/s; one hour of 1080p
streaming is ~3 GB. The original NoisyCompany had no cap and downloaded whole pages with all
their size, ~25 levels deep, every 3-6 s: easily several GB per day.

How the footprint is kept small:

- responses cut at 192 KB (`max_response_kb`), HTML only: no image, script, CSS or video;
- gzip/deflate accepted (Wikipedia pages travel at ~30-70 KB);
- DNS sessions (~300 bytes) are almost half of all sessions;
- daily hard cap, hourly action cap, and the budget is spread over active hours;
- no activity outside active hours (night by default).

## Effect on your browsing

- **Throughput**: a few kbit/s on average, peaks of one page download (~0.1-0.5 s of a
  slow ADSL line). Not measurable by the user on any broadband link.
- **Latency / bufferbloat**: one TCP connection at a time, never parallel; no sustained
  flow, so router queues stay empty.
- **Contention**: netwatch (Linux) pauses NoisyCompany while your traffic exceeds 400 kbit/s, so
  video calls and downloads never compete with it.
- **CPU / memory**: idle most of the time, `nice 10`, systemd unit capped at 5% CPU and
  64 MB. Measured peak RSS ~26 MB (Python 3.14).
- **DNS cache**: lookups add entries to your local cache; harmless.
- **Possible downsides**: CAPTCHAs on some sites if limits are raised; on metered mobile
  data, use `eco`.

## Ecology

Network energy per GB is disputed. We give a range rather than a single number:

- high: 0.06 kWh/GB (Aslan et al., 2018, data for 2015, averaged model);
- low: 0.005 kWh/GB (recent fixed-network estimates; efficiency roughly doubles every
  ~2 years);
- marginal view: network equipment power barely changes with load, so the real extra
  energy of small flows is close to zero. The cost that matters is on servers visited and
  on the device that stays awake.

| Preset | Network energy/month | CO2e/month (France, 50 g/kWh) | CO2e/month (EU avg, 250 g/kWh) |
|---|---|---|---|
| eco | 0.3-4 Wh | 0.02-0.2 g | 0.1-1 g |
| balanced | 2-27 Wh | 0.1-1.4 g | 0.6-7 g |
| max | 9-108 Wh | 0.5-5 g | 2-27 g |

For comparison, one hour of HD streaming is ~3 GB, i.e. 15-180 Wh by the same method.

**Device energy dominates.** Running NoisyCompany on an always-on box (router, NAS, Raspberry Pi
at 2-3 W) adds almost nothing. Keeping a laptop awake for it would cost far more than the
traffic: NoisyCompany never prevents sleep, and should not be the reason a machine stays on.

**Server side.** Every page is a request to someone's server. Defaults (robots.txt,
20 s per host, mostly Wikipedia and large sites) keep this negligible. Do not point
personas at small hobby sites with high frequency.
