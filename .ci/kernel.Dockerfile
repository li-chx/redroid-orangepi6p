# SPDX-License-Identifier: MIT
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --no-install-recommends -y \
    ca-certificates git python3 build-essential bc bison flex libssl-dev libelf-dev \
    libncurses-dev kmod file cpio rsync xz-utils dpkg-dev grub-common \
    && rm -rf /var/lib/apt/lists/*
