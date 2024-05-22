# Small, non-root, read-only friendly image. No runtime dependency beyond CPython.
FROM python:3.13-alpine AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.13-alpine
COPY --from=build /install /usr/local
RUN adduser -D -H -u 10001 noisycompany
USER 10001
ENV XDG_STATE_HOME=/state
VOLUME ["/state"]
# netwatch needs the host network namespace to see the user's traffic:
#   docker run --network host --read-only -v noisycompany-state:/state noisycompany
ENTRYPOINT ["noisycompany"]
CMD ["run"]
