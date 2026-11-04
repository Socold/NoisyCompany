# Grafana dashboard

1. `noisycompany features on metrics` (Prometheus text on `127.0.0.1:9789/metrics`).
2. Scrape it (Prometheus runs on the same host, the endpoint is localhost only):

   ```yaml
   scrape_configs:
     - job_name: noisycompany
       scrape_interval: 1m
       static_configs: [{ targets: ["127.0.0.1:9789"] }]
   ```

3. Grafana > Dashboards > Import > `noisycompany-dashboard.json`, pick the Prometheus
   data source.

Panels: today's bytes and share of the cap, metered flag, sessions, noise bit rate,
pages (ok / failed / robots.txt), DNS lookups, back-offs (your traffic, budget).
