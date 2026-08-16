FROM python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

ARG WHEEL=dist/nexus_os-0.2.0a3-py3-none-any.whl
COPY ${WHEEL} /tmp/nexus_os-0.2.0a3-py3-none-any.whl
RUN python -m pip install --no-cache-dir /tmp/nexus_os-0.2.0a3-py3-none-any.whl \
    && rm /tmp/nexus_os-0.2.0a3-py3-none-any.whl \
    && groupadd --system --gid 10001 rad \
    && useradd --system --uid 10001 --gid rad --create-home --home-dir /home/rad rad

USER 10001:10001
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["rad"]
CMD ["--help"]
