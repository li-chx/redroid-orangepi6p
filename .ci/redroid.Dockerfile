# SPDX-License-Identifier: MIT
FROM docker:28-cli AS docker-cli
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --no-install-recommends -y \
    ca-certificates python3 clang binutils p7zip-full e2fsprogs gzip tar \
    && rm -rf /var/lib/apt/lists/*
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
