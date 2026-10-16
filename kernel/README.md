# Orange Pi 6 Plus ReDroid 内核

为 Orange Pi 6 Plus 官方 Debian ARM64 系统构建 **`6.6.89-cix-redroid`**，包含 Binder、Android 网络配置和配套 GPU / NPU / VPU / ISP 模块。版本名没有末尾的 `2`。

## 构建与下载

在 CNB 页面点击 **构建内核 deb**，完成后下载当前提交附件中的 `kernel-<构建ID>.tar`。配置与下载方式见 [CI 说明](../docs/CI.md)。

也可在 x86_64 Linux 上用 [.ci/kernel.Dockerfile](../.ci/kernel.Dockerfile) 中的依赖环境构建：

```sh
JOBS=8 bash kernel/build.sh
```

脚本下载固定源码与编译器到 `kernel/work/`，合并厂商完整配置和 [redroid.config](redroid.config)，构建 Image、树内模块和 DTB，再为同一 release 重编六个厂商模块：

- `memory_group_manager`、`protected_memory_allocator`、`mali_kbase`；
- NPU `aipu`、VPU `amvx`、ISP `armcb_isp_v4l2`。

`dist/kernel/` 包含 deb、完整对应源码归档、项目构建脚本源码包、最终配置、输入锁定清单、构建信息和 `SHA256SUMS`。不把固件或原厂闭源用户态库重新打进内核包，继续使用板上已有配套。

## 安装与启动项

在开发板上解开下载的 TAR，在产物目录执行：

```sh
sha256sum -c SHA256SUMS
sudo apt install ./linux-image-6.6.89-cix-redroid_*_arm64.deb
```

包名为 `linux-image-6.6.89-cix-redroid`。安装时写入版本化的 `/boot/vmlinuz-6.6.89-cix-redroid`、模块和 DTB，运行 `depmod`，然后自动注册启动项：

1. 检查当前是 Debian、ARM64、EFI 启动，根文件系统位于可识别 PARTUUID 的普通磁盘分区。
2. 查找根磁盘上唯一的 FAT EFI 分区；已挂载时使用已有挂载点，未挂载时临时挂载并在结束后卸载。
3. 核对分区中的 `EFI/BOOT/BOOTAA64.EFI` 与 `grub/grub.cfg`，要求存在唯一的 Orange Pi 6 Plus 原厂 ACPI `/Image` 入口，且其中根分区 PARTUUID 与当前系统一致。
4. 使用 GRUB 语法检查器检查新配置，将新 Image 复制为 EFI 分区的 `/Image-redroid`，添加 ID 为 `orangepi6p-redroid` 的启动项并设为默认，菜单等待 5 秒。新入口保留原厂参数并加入 `module_blacklist=panthor`，避免 Panthor 抢占厂商 Mali 驱动。
5. 保留原厂 `/Image`、原厂菜单和模块，将配置备份放在 `/var/lib/orangepi6p-redroid-kernel/`，读回检查后结束。

**安装不会自动重启。** 重启后用 `uname -r` 核对是否为 `6.6.89-cix-redroid`，再运行项目的宿主/容器检查。注册失败会让安装返回错误，不会静默声称成功；不要把“包已解包”当作已完成启动设置。

这套启动集成针对已记录的官方 **ACPI、无 initrd、同盘 EFI 分区** 布局，不对普通 PC GRUB、LVM/加密根分区、跨盘或无法识别的启动布局作自动修改。它不会调用 `grub-install`、写固件、修改 UEFI BootOrder 或删除其他内核。

配置文件是 `/etc/orangepi6p-redroid-kernel.json`：`esp_device` 默认为自动发现，`make_default` 默认为 `true`。需要指定同盘 ESP 或只添加菜单时可修改它，再运行 `sudo dpkg-reconfigure linux-image-6.6.89-cix-redroid`。

若新内核不能正常使用，可在启动菜单选择保留的原厂入口。卸载前先启动其他内核，再执行 `sudo apt remove linux-image-6.6.89-cix-redroid`；卸载会移除受管理的菜单部分，保留 EFI 镜像和配置备份以供恢复。正在运行本内核时拒绝卸载。

## 源码与配套边界

固定输入见 [sources.lock.json](sources.lock.json)：

- [Orange Pi Linux](https://github.com/orangepi-xunlong/linux-orangepi)，`orange-pi-6.6-cix` 路线，提交 `f41a4f0b22c0f85a645aa207435761a0123feeaf`。
- [component_cix-next](https://github.com/orangepi-xunlong/component_cix-next)，提交 `ba3bac4167cd5f115f3eaf4717356d2b3cb923d5`，仅检出公开 GPU / NPU / VPU / ISP 源码。
- 厂商配置基线来自此前保存的原板 `/proc/config.gz`，文件及 SHA 已固定；不能用小配置片段代替这份完整硬件基线。
- Arm GNU Toolchain 12.3.Rel1，下载文件 SHA256 固定。

[vendor-o-build.patch](vendor-o-build.patch) 修正 9 个 Realtek Makefile 中的 23 处路径，用于源码树外的 `O=` 构建，不修改 GPU / VPU 功能。构建拒绝混入其他内核源码修改。公开 GPU 的 474 份、NPU 的 45 份 C/头文件/构建文件，已与原实验使用源码逐项比对一致。

历史实机验收的 release 是 `6.6.89-cix-redroid2`，对应验证记录保留原名；改用新 release 后的构建和打包不自动继承“已在开发板启动”的结论。已有内核具备所需功能的使用者可以只构建 ReDroid 镜像。固件与源代码的原始逐位对应关系仍有限制，不用 CI 构建替换板上固件。

Linux、驱动和补丁保留原许可，原创构建及启动注册脚本采用 MIT；下载包包含对应源码。详见 [NOTICE](../NOTICE) 和 [验证记录](../docs/VALIDATION.md)。
