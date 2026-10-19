# 验证记录

本文汇总截至 2026-10-19 确认的构建和实机测试结果。使用方法见 [README](../README.md)，版本配套和已知问题见 [技术说明](TECHNICAL.md)。

## 验证范围

| 对象 | 已有结果 | 结果的适用范围 |
| --- | --- | --- |
| 早期适配环境，内核 `6.6.89-cix-redroid2` | Android 启动、Mali 图形加速、Vulkan 和 CIX H.264 硬件编码通过实机测试 | 证明该驱动组合可以工作；不代表后续发布的全部产物已通过实机验收。 |
| 2026-10-15 构建的空数据 Android 实例 | 启动、显示配置、硬件编码及视频解码检查通过 | 覆盖首次启动和短时录屏功能，不包含游戏、长期稳定性或性能基准。 |
| 2026-10-17 发布的 `6.6.89-cix-redroid` 内核包 | CNB 构建与发布成功，已在开发板安装并配合发布镜像验证，运行正常 | 使用者确认的实机结果；Android 复用已有数据卷。 |
| 2026-10-17 发布的 ReDroid 镜像 `build-cnb-9rb-1k53vpcv5` | CNB ARM64 构建与发布成功，与发布内核配套测试正常，游戏正常运行 | 覆盖复用已有数据卷的运行场景；该组合的空数据首次启动需单独验证。 |

## 2026-10-17 发布产物

内核和镜像均由源码提交 `52c099f5d467b35a018ffb8d24acbfc6e0223895` 构建。固定产物标识如下，便于核对下载结果和报告问题。

### 内核

- 构建日志：[cnb-u9c-1k53v2noi](https://cnb.cool/li_chx/redroid-orangepi6p/-/build/logs/cnb-u9c-1k53v2noi)。源码准备、测试、完整内核和六个厂商模块编译、打包、上传均成功。
- 发布标签：`kernel-6.6.89-cix-redroid-20261017`，见 [Release 列表](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases)。下载与校验命令见 [README](../README.md#1-下载并安装宿主内核)。
- 附件：`kernel-cnb-u9c-1k53v2noi.tar`，224,409,600 字节，SHA256 为 `4b3f721c9287a245116f20c992ec52337a190f7dcab5d194c0741151aeda5148`。
- 下载后已核对外层归档和包内全部 10 项校验值。`build-info.json` 记录的源提交、构建 ID 和 vendor 快照提交与该构建一致，模块总数为 951。

编译验证包括模块 ARM64 架构、模块版本标记（vermagic）、Mali 模块加载依赖顺序、`depmod` 依赖生成，以及 deb 内实际文件与打包清单的一致性。启动项注册通过隔离测试；该内核 deb 已在开发板安装，并与发布镜像配套完成实机验证，结果见下文。

### ReDroid 镜像

- 构建日志：[cnb-9rb-1k53vpcv5](https://cnb.cool/li_chx/redroid-orangepi6p/-/build/logs/cnb-9rb-1k53vpcv5)。
- 固定镜像地址：`docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:build-cnb-9rb-1k53vpcv5`。
- 制品库镜像摘要：`sha256:988411f51474ab25b2c5953dad7be5dd35ffb6f42ced3724d155be620c1f9308`，平台为 ARM64。

发布时 `14` 标签与上述固定标签指向同一镜像；`14` 会随成功构建更新，核对该次发布请使用固定标签或摘要。

## 实机功能测试

### 发布内核与镜像配套验证（2026-10-19 确认）

使用者确认，上述发布的 ReDroid 镜像和 `6.6.89-cix-redroid` 内核 deb 均已部署到 Orange Pi 6 Plus 开发板，配套测试正常，游戏也正常运行。Android 数据复用已有 volume（数据卷），保留了原有应用和数据。

该结果验证了发布内核与镜像在已有数据卷上的运行情况。空数据首次启动、独立编码测试和量化性能结果仍按各自的测试记录区分。

### 早期驱动组合

早期实机环境使用 Orange Pi 6 Plus、`6.6.89-cix-redroid2` 内核、Mali 内核驱动 r53p0 / UK1.36，以及官方 Android 14 v1.0.1 的 r49p0 用户态驱动。该环境已运行《明日方舟：终末地》，并通过 scrcpy 使用 H.264 硬件编码，使用者确认音画正常。这些驱动与编码检查的详细结果属于早期适配环境；发布产物的配套验证见上一节。

### 2026-10-15 空数据实例

单独构建的镜像在新建的空数据容器中测试，镜像 ID 为 `sha256:0054f9561dab8f6a211bd18eeab2725eedfd4696ad74d6be14e03f64bc31b6c5`。测试结果：

- Android 的 `sys.boot_completed` 为 `1`，EGL / Vulkan 选择 Mali，OpenGL ES 渲染器识别为 ARM Mali，CIX Codec2 服务处于 `running` 状态。
- 显示配置为 1920×1080、120 Hz；容器只绑定项目内的数据目录到 `/data`，没有自动创建的匿名数据卷。
- 指定 `c2.cix.avc.encoder`，以 1920×1080、8 Mbps 录制 8 秒 H.264 视频。编码期间确认厂商服务持有 `/dev/video1`，输出 229 帧，`ffprobe` 检查和完整 CPU 解码均无错误。
- 设置界面人工检查正常，Vulkan 设备枚举包含 Mali。

录制内容为 HOME / 设置界面及导航动画，未在该实例安装游戏。229 帧是这段短录的输出数量，不能用作持续游戏帧率、投屏延迟或性能上限结论。

## 构建与脚本验证

以下检查覆盖构建输入和工具行为，可帮助定位构建问题；它们不需要启动 Android，也不能代替实机测试。

| 检查范围 | 已验证内容 |
| --- | --- |
| 厂商文件 | 从锁定官方镜像提取的 48 个文件摘要匹配；资源包下载、导入和逐文件校验通过；损坏文件、缺失文件、路径越界、链接及重复项会被拒绝。 |
| 基础镜像 | 兼容锁定镜像的两种 ID 表示；拒绝错误架构和声明自动创建数据卷的基础镜像。 |
| Android 头文件 | 按路径、文件内容摘要和文件数校验，允许压缩包元信息变化；文件内容、路径和重复项变化会被拒绝。 |
| 镜像打包 | 2026-10-16 在 amd64 Linux 上完成 ARM64 交叉构建，从未启动的容器读回全部 60 份安装文件，核对摘要与 root 所有权。2026-10-17 的原生 ARM64 CI 结果见上文。 |
| 内核源码 | 固定 CNB 快照初始化、来源清单与目录内容标识校验通过；实际构建的驱动源码修改会被拒绝；内核构建补丁可重复应用。 |
| 工具链缓存 | 验证 SHA256、执行权限和符号链接恢复、缓存复用，以及校验或解压失败时的处理。 |
| 内核安装与打包 | 隔离测试覆盖 EFI 分区选择、启动菜单重复注册、错误布局拒绝、失败恢复、卸载保护、模块检查、实际 deb 内容和对应源码打包。生成菜单通过 `grub-script-check` 语法检查。 |
| 源码导出 | 包含项目源码、配置、文档和文件校验清单，排除厂商二进制、内核子模块工作树及构建和应用数据目录。 |

内核回归测试在 2026-10-17 的 Termux 环境中执行 25 项，24 项通过，1 项因缺少 `grub-script-check` 跳过；启动菜单语法检查在此前具备该工具的 Linux 环境中通过。运行测试的命令为 `python3 kernel/tests/test_kernel.py`；镜像相关测试入口见 [.cnb.yml](../.cnb.yml)。

## 在开发板上复查

先按 [README](../README.md) 准备宿主和镜像。检查已启动的默认容器：

```sh
python3 scripts/check-host.py
python3 scripts/check-runtime.py --name redroid
```

`check-runtime.py` 检查启动完成、刷新率策略、Mali 渲染器、Codec2 服务状态和数据挂载，并将结果写入 `work/runtime-redroid.json`。服务注册成功不等于已经完成一次硬件编码。

如需复查短时编码，开发板还需安装提供 `ffmpeg` / `ffprobe` 的 FFmpeg 软件包。使用从未用过的容器名和空数据目录；下例假设不存在 `redroid-validation` 容器及 `data/redroid-validation/` 目录，且本机端口 5556 空闲：

```sh
docker pull docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:build-cnb-9rb-1k53vpcv5
python3 scripts/run.py \
  --image docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:build-cnb-9rb-1k53vpcv5 \
  --name redroid-validation --port 5556
python3 scripts/smoke-test.py --name redroid-validation --fresh-test-instance
```

测试会打开 HOME / 设置界面并录屏，因此只用于新建的空数据实例。输出位于 `work/verification/redroid-validation/`，包括编码日志、视频、解码检查结果、截图和 Vulkan 枚举。检查视频和截图后，可用 `docker stop redroid-validation` 停止测试实例。

## 尚未验证与已知问题

- 2026-10-17 发布的内核与镜像组合的空数据首次启动。
- H.265 实际编码、全部解码格式、持续 120 fps、长期稳定性及量化延迟。
- 其他基础镜像、厂商驱动版本或设备的兼容性。
- 早期游戏测试曾出现重开后黑屏，日志包含 `QueueSignalReleaseImageANDROID failed: -3`；一次容器重启后恢复，根因尚未定位。
