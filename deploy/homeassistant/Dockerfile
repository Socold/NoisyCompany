ARG BUILD_FROM
FROM ${BUILD_FROM}
USER root
COPY run.py /run.py
# Home Assistant mounts /data (options.json + persistent state).
ENTRYPOINT ["python3", "/run.py"]
