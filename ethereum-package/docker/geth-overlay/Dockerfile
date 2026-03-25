FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates netbase \
  && rm -rf /var/lib/apt/lists/*

COPY geth /usr/local/bin/geth

# ---- Add these two lines ----
COPY blocked_addresses.json /etc/geth/blocked_addresses.json
ENV GETH_CENSORSHIP_CONFIG=/etc/geth/blocked_addresses.json
# ----------------------------

RUN chmod +x /usr/local/bin/geth && /usr/local/bin/geth version

ENTRYPOINT ["geth"]
