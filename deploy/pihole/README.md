# Pi-hole / AdGuard Home box

The resolver box is the best place for DNS noise (every query of the household goes
through it) and for measuring how separable the noise is (it logs every query).

## Run

```bash
cd deploy/pihole
mkdir -p state && sudo chown 10001:10001 state
docker compose up -d
```

The box must resolve through Pi-hole itself (`/etc/resolv.conf` pointing to
`127.0.0.1`), which is the default on a Pi-hole host.

## Measure

Run it a few days, then compare the noise with the real queries of the same period.
Work on a copy of the database: Pi-hole keeps it open in WAL mode.

```bash
sudo sqlite3 /etc/pihole/pihole-FTL.db ".backup /tmp/ftl-copy.db"
docker compose run --rm -v /tmp/ftl-copy.db:/tmp/ftl.db:ro noisycompany \
  study --noise /state/labelled.jsonl --human /tmp/ftl.db --exclude-noise-hosts
```

AdGuard Home: pass `querylog.json` (in its work directory) instead of the database.

## What you will see in Pi-hole

Decoy queries show up in the query log and the statistics, tagged with the box's own
address as client. Group them with a Pi-hole client group if you want them out of your
dashboards. Blocklists still apply to them: blocked decoys are simply not resolved.
