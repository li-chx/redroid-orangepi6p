#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build the kernel plus all six vendor modules, then create a boot-integrated deb.
set -Eeuo pipefail
kernel=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
work="$kernel/work"
mkdir -p "$work/tmp" "$work/logs"
export TMPDIR="$work/tmp"
exec 9> "$work/build.lock"
flock -n 9 || { echo 'Another kernel build is running' >&2; exit 1; }
exec > >(tee "$work/logs/build.log") 2>&1
trap 'echo "Kernel build failed at line $LINENO; see kernel/work/logs/" >&2' ERR
jobs=${JOBS:-8}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 1; }
[[ "$(uname -m)" == x86_64 ]] || { echo 'Pinned toolchain requires an x86_64 build host' >&2; exit 1; }

python3 "$kernel/fetch-sources.py"
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git -c safe.directory="$kernel/.." -C "$kernel/.." log -1 --format=%ct)}
[[ "$SOURCE_DATE_EPOCH" =~ ^[0-9]+$ ]] || { echo 'Invalid SOURCE_DATE_EPOCH' >&2; exit 1; }
export SOURCE_DATE_EPOCH
export KBUILD_BUILD_USER=builder KBUILD_BUILD_HOST=cnb KBUILD_BUILD_VERSION=1
KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH" '+%a %b %d %T UTC %Y')
export KBUILD_BUILD_TIMESTAMP
src="$kernel/upstream/linux"
components="$kernel/upstream/components/cix_opensource"
out="$work/build"
stage="$work/stage"
cross="$work/toolchains/arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-"
expected=6.6.89-cix-redroid
km=(make -C "$src" O="$out" ARCH=arm64 CROSS_COMPILE="$cross" LOCALVERSION=)
mkdir -p "$out"

# Reject unrelated local source changes and apply only the pinned O= patch.
python3 - "$src" "$kernel/vendor-o-build.patch" <<'PY'
from pathlib import Path
import subprocess, sys
src, patch = sys.argv[1:]
diff = subprocess.check_output(['git', '-C', src, 'diff', '--no-ext-diff', '--full-index', 'HEAD'])
if diff:
    # Reversing our patch must leave the checkout identical to the fixed commit.
    subprocess.run(['git', '-C', src, 'apply', '--reverse', '--check', patch], check=True)
    subprocess.run(['git', '-C', src, 'apply', '--reverse', patch], check=True)
    try:
        subprocess.run(['git', '-C', src, 'diff', '--quiet', 'HEAD'], check=True)
    finally:
        subprocess.run(['git', '-C', src, 'apply', patch], check=True)
else:
    subprocess.run(['git', '-C', src, 'apply', '--check', patch], check=True)
    subprocess.run(['git', '-C', src, 'apply', patch], check=True)
PY
git -C "$kernel/upstream/components" diff --exit-code HEAD
cp "$kernel/configs/vendor-6.6.89-cix.config" "$out/.config"
"$src/scripts/kconfig/merge_config.sh" -m -O "$out" "$out/.config" "$kernel/redroid.config"
"$src/scripts/config" --file "$out/.config" --set-str LOCALVERSION '-cix-redroid' --disable LOCALVERSION_AUTO
"${km[@]}" olddefconfig
for option in ARM64 MODULES MODULE_COMPRESS_NONE ANDROID_BINDER_IPC ANDROID_BINDERFS MEMFD_CREATE IP_ADVANCED_ROUTER IP_MULTIPLE_TABLES IPV6_MULTIPLE_TABLES FIB_RULES; do
    grep -qx "CONFIG_${option}=y" "$out/.config" || { echo "Missing CONFIG_$option" >&2; exit 1; }
done
! grep -qx 'CONFIG_MODULE_SIG_FORCE=y' "$out/.config"
grep -qx 'CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"' "$out/.config"
[[ "$("${km[@]}" -s --no-print-directory kernelrelease)" == "$expected" ]] || { echo 'Unexpected kernelrelease' >&2; exit 1; }
cp "$out/.config" "$work/logs/config.final"
"${km[@]}" -j"$jobs" Image modules dtbs

# Build from clean work copies so upstream source remains suitable for redistribution.
vendor="$work/vendor"
rm -rf "$vendor"
mkdir -p "$vendor"
copy_source() {
    mkdir -p "$2"
    tar -C "$1" --exclude='.git' --exclude='*.o' --exclude='*.ko' --exclude='*.cmd' \
        --exclude='*.o.d' --exclude='*.mod' --exclude='*.mod.c' --exclude='Module.symvers' \
        --exclude='modules.order' --exclude='built-in.a' -cf - . | tar -C "$2" --no-same-owner -xf -
}
copy_source "$components/gpu/gpu_kernel" "$vendor/gpu"
copy_source "$components/npu/npu_driver/driver" "$vendor/npu"
copy_source "$components/vpu/vpu_driver" "$vendor/vpu"
copy_source "$components/isp/isp_driver" "$vendor/isp"
gpu_env=(env KDIR="$out" ARCH=arm64 CROSS_COMPILE="$cross" LOCALVERSION=
    CONFIG_MALI_BASE_MODULES=y CONFIG_MALI_MEMORY_GROUP_MANAGER=y
    CONFIG_MALI_PROTECTED_MEMORY_ALLOCATOR=y CONFIG_MALI_PLATFORM_NAME=sky1
    CONFIG_MALI_CSF_SUPPORT=y CONFIG_MALI_CIX_POWER_MODEL=y)
"${gpu_env[@]}" make -C "$vendor/gpu/drivers/base/arm" clean
"${gpu_env[@]}" make -C "$vendor/gpu/drivers/gpu/arm" clean
"${gpu_env[@]}" make -C "$vendor/gpu/drivers/base/arm" -j"$jobs" all
"${gpu_env[@]}" make -C "$vendor/gpu/drivers/gpu/arm" -j"$jobs" all
# PWD is required by the vendor include paths, including recursive Kbuild calls.
npu_env=(env PWD="$vendor/npu" COMPASS_DRV_BTENVAR_KPATH="$out" ARCH=arm64 CROSS_COMPILE="$cross" LOCALVERSION=
    COMPASS_DRV_BTENVAR_KMD_VERSION=5.11.0 BUILD_AIPU_VERSION_KMD=BUILD_ZHOUYI_V3
    BUILD_TARGET_PLATFORM_KMD=BUILD_PLATFORM_SKY1 BUILD_NPU_DEVFREQ=y)
"${npu_env[@]}" make -C "$vendor/npu" clean
"${npu_env[@]}" make -C "$vendor/npu" -j"$jobs" all
make -C "$vendor/vpu/driver" KDIR="$out" ARCH=arm64 CROSS_COMPILE="$cross" LOCALVERSION= -j"$jobs" mono_v4l2
"${km[@]}" M="$vendor/isp" PWD="$vendor/isp" PATH_ROOT="$src" -j"$jobs" modules

rm -rf "$stage"
mkdir -p "$stage/boot" "$stage/lib/modules/$expected/extra"
"${km[@]}" INSTALL_MOD_PATH="$stage" DEPMOD=true modules_install
install -m 0644 \
    "$vendor/gpu/drivers/base/arm/memory_group_manager/memory_group_manager.ko" \
    "$vendor/gpu/drivers/base/arm/protected_memory_allocator/protected_memory_allocator.ko" \
    "$vendor/gpu/drivers/gpu/arm/midgard/mali_kbase.ko" \
    "$vendor/npu/aipu.ko" "$vendor/vpu/driver/amvx.ko" "$vendor/isp/armcb_isp_v4l2.ko" \
    "$stage/lib/modules/$expected/extra/"
rm -f "$stage/lib/modules/$expected/build" "$stage/lib/modules/$expected/source"
install -m 0644 "$out/arch/arm64/boot/Image" "$stage/boot/vmlinuz-$expected"
install -m 0644 "$out/System.map" "$stage/boot/System.map-$expected"
install -m 0644 "$out/.config" "$stage/boot/config-$expected"
"${km[@]}" INSTALL_DTBS_PATH="$stage/boot/dtb-$expected" dtbs_install
depmod -b "$stage" -e -F "$out/System.map" "$expected" 2>&1 | tee "$work/logs/depmod.log"
[[ ! -s "$work/logs/depmod.log" ]] || { echo 'depmod reported unresolved symbols' >&2; exit 1; }
modprobe -d "$stage" -S "$expected" --show-depends mali_kbase > "$work/logs/mali-load-plan.txt"
python3 "$kernel/package.py"
