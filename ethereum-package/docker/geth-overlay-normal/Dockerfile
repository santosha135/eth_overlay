FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates netbase \
    && rm -rf /var/lib/apt/lists/*

COPY geth /usr/local/bin/geth

RUN chmod +x /usr/local/bin/geth && /usr/local/bin/geth version

ENTRYPOINT ["geth"]
