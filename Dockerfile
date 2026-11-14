# Small, non-root, read-only friendly image. No runtime dependency beyond CPython.
FROM python:3.15-alpine AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.15-alpine
COPY --from=build /install /usr/local
RUN adduser -D -H -u 10001 noisycompany \
    && mkdir -p /state && chown 10001:10001 /state && chmod 700 /state
# /state must exist and belong to the user: a new named volume copies this ownership.
USER 10001
ENV XDG_STATE_HOME=/state
VOLUME ["/state"]
# netwatch needs the host network namespace to see the user's traffic:
#   docker run --network host --read-only -v noisycompany-state:/state noisycompany
# The health check exits 0 while the daemon writes its heartbeat (switch
# appliance_packages on; it always succeeds when the switch is off). It runs the
# light module, not the full CLI: under `cpus: 0.1` the full CLI takes
# 25-30 s, the light module ~15 s (mostly interpreter startup). Hence 60 s.
HEALTHCHECK --interval=2m --timeout=60s --start-period=1m CMD ["python", "-m", "noisycompany.health"]
ENTRYPOINT ["noisycompany"]
CMD ["run"]
