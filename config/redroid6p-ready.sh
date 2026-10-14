#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
fps=$(getprop ro.boot.redroid_fps)
case "$fps" in ''|*[!0-9]*) fps=60 ;; esac
settings put system min_refresh_rate "$fps.0"
settings put system peak_refresh_rate "$fps.0"
log -t redroid6p "Refresh policy configured for $fps Hz"
