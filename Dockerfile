ARG BASE_IMAGE=redroid/redroid@sha256:46478a567194aed24cd0877d4434a9e58b534d4aad30931eb21999a52f2ce131
FROM ${BASE_IMAGE}
LABEL org.opencontainers.image.title="Orange Pi 6 Plus ReDroid Android14 GPU/VPU"
# Locally imported factory files; this directory is excluded from source releases.
COPY --chown=0:0 work/rootfs/ /
CMD ["androidboot.use_memfd=1", "androidboot.redroid_gpu_mode=guest", "androidboot.redroid_width=1920", "androidboot.redroid_height=1080", "androidboot.redroid_dpi=160", "androidboot.redroid_fps=120"]
