# Orange Pi 6 Plus ReDroid 内核

为 Orange Pi 6 Plus 官方 Debian ARM64 系统构建 **`6.6.89-cix-redroid`**，包含 Binder（Android 进程间通信）、Android 所需的网络配置，以及图形、神经网络、视频和图像处理驱动（GPU / NPU / VPU / ISP）。

## 构建与下载

已发布的 [内核下载包](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases/download/kernel-6.6.89-cix-redroid-20261017/kernel-cnb-u9c-1k53v2noi.tar) 来自成功构建的提交 `52c099f`，包含 deb、对应源码、配置和校验清单。[Release 列表](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases)提供长期保存的原始附件及外层 SHA256 文件。

自行构建时，在 CNB **分支详情页**点击 **构建内核 deb**，无需填写 Android 资源包地址；成功后下载触发构建的提交附件 `kernel-<构建ID>.tar`，提交附件保留 7 天。完整的 Docker / 宿主手动构建步骤可展开 [项目 README](../README.md#1-下载并安装宿主内核) 中的说明，流水线配置见 [CI 文档](../docs/CI.md#内核-deb)。

也可在 x86_64 Linux 上用 [.ci/kernel.Dockerfile](../.ci/kernel.Dockerfile) 中的依赖环境构建：

```sh
git submodule update --init --recursive
JOBS=8 bash kernel/build.sh
```

Linux 和厂商驱动源码由 [CNB vendor 快照](https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor) 提供，作为 Git 子模块检出到 `kernel/vendor-snapshot/`。CNB 流水线自动初始化子模块；本地构建需先执行上面的初始化命令。项目源码压缩包不包含该子模块，构建内核需使用 Git 工作树。

编译器、编译中间文件和日志位于 `kernel/work/`。脚本验证源码版本，合并厂商完整配置和 [redroid.config](redroid.config)，生成内核镜像 Image、内核自带模块和设备树文件（DTB），再为同一内核版本编译六个厂商模块：

- `memory_group_manager`、`protected_memory_allocator`、`mali_kbase`；
- NPU `aipu`、VPU `amvx`、ISP `armcb_isp_v4l2`。

`dist/kernel/` 包含 deb、对应的内核与驱动源码归档、项目构建脚本源码包、最终配置、输入锁定清单、构建信息和 `SHA256SUMS`。内核包沿用开发板已有的配套固件和原厂用户态库，不包含它们。

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

自动注册要求官方 Debian 的启动布局：通过 ACPI 描述硬件、直接加载内核而不使用 initrd（初始内存盘），且 EFI 系统分区（ESP）与根分区位于同一磁盘。普通 PC GRUB、LVM、加密根分区、跨盘或无法识别的布局不在自动配置范围内。脚本不会调用 `grub-install`、写固件、修改 UEFI BootOrder 或删除其他内核。

配置文件是 `/etc/orangepi6p-redroid-kernel.json`：`esp_device` 默认为自动发现，`make_default` 默认为 `true`。需要指定同盘 ESP 或只添加菜单时可修改它，再运行 `sudo dpkg-reconfigure linux-image-6.6.89-cix-redroid`。

若新内核不能正常使用，可在启动菜单选择保留的原厂入口。卸载前先启动其他内核，再执行 `sudo apt remove linux-image-6.6.89-cix-redroid`；卸载会移除受管理的菜单部分，保留 EFI 镜像和配置备份以供恢复。正在运行本内核时拒绝卸载。

## 源码与配套边界

固定输入见 [sources.lock.json](sources.lock.json)：

- [Orange Pi Linux](https://github.com/orangepi-xunlong/linux-orangepi)，`orange-pi-6.6-cix` 分支，提交 `f41a4f0b22c0f85a645aa207435761a0123feeaf`。
- [component_cix-next](https://github.com/orangepi-xunlong/component_cix-next)，提交 `ba3bac4167cd5f115f3eaf4717356d2b3cb923d5`；只构建和打包锁定清单所列的四个公开 GPU / NPU / VPU / ISP 源码目录。
- 完整硬件配置基线为 [vendor-6.6.89-cix.config](configs/vendor-6.6.89-cix.config)，提取自 Orange Pi 6 Plus 官方 Debian `6.6.89-cix` 内核的 `/proc/config.gz`，SHA256 固定在锁定清单中。构建时在这份完整配置上叠加 `redroid.config`。
- Arm GNU Toolchain 12.3.Rel1，下载文件按固定 SHA256 校验，解压完成后才写入工具链缓存。

[.gitmodules](../.gitmodules) 注册 `kernel/vendor-snapshot` 一个子模块，指向 CNB vendor 仓库；其中 `linux/` 是完整 Linux 源码，`components/` 只含上述四个公开驱动目录，没有嵌套子模块。主仓库与 `sources.lock.json` 固定同一个快照提交，锁定清单同时记录上游提交和 Git tree ID（目录内容标识），快照内的 `snapshot.json` 记录来源。源码初始化从 CNB 下载，Arm 编译器按固定 URL 和 SHA256 单独下载。

内核流水线显式开启 `git.submodules`，设置 `remote: false`，不跟踪分支最新版本；镜像流水线关闭子模块。行为依据 [CNB Git 配置](https://docs.cnb.cool/zh/build/grammar.html#git)。

`fetch-sources.py` 验证已初始化的 CNB 快照、锁定提交、来源清单、目录内容标识和所需驱动目录，不负责克隆或切换源码。缺失子模块时应先执行 `git submodule update --init --recursive`；提交或内容不符时构建会报错。

构建会在快照的 `linux/` 中应用下述 Makefile 补丁，因此构建后 Git 显示子模块有修改属于预期，重复构建会核对并保留同一补丁。其他内核源码修改，以及锁定清单所列四个驱动目录中的暂存或未暂存修改，都会被拒绝。对应源码包附带快照来源清单，构建信息记录 CNB 快照提交和原始上游提交。

[vendor-o-build.patch](vendor-o-build.patch) 修正 Realtek Makefile 中的路径，使编译输出可放在源码目录之外（`O=` 构建），不改变 GPU / VPU 功能。

早期实机测试使用 `6.6.89-cix-redroid2`。2026-10-19，使用者确认这里发布的 `6.6.89-cix-redroid` 内核 deb 已在开发板安装，与发布的 ReDroid 镜像配套测试正常，游戏也正常运行；Android 复用了已有数据卷。已有兼容内核的使用者可以只构建 ReDroid 镜像；完整版本与测试对应关系见 [验证记录](../docs/VALIDATION.md)。

Linux、驱动和补丁保留原许可，原创构建及启动注册脚本采用 MIT；下载包包含对应源码。详见 [NOTICE](../NOTICE) 和 [验证记录](../docs/VALIDATION.md)。
