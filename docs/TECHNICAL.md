# 技术说明

日常构建、启动和连接步骤见 [README](../README.md)。本文面向需要了解驱动配套、排查运行问题或修改构建脚本的读者。CNB 构建与发布见 [CI 说明](CI.md)，内核安装与恢复见 [内核说明](../kernel/README.md)。

## 实现与适用范围

本项目适配 Orange Pi 6 Plus / CIX P1 上的 Android 14 ReDroid。Android 使用虚拟显示，图形和视频处理通过容器内的厂商驱动访问宿主设备，不接管宿主显示器。

| 组件 | 在本项目中的作用 |
| --- | --- |
| Mali EGL / OpenGL ES / Vulkan 驱动 | 为 Android 应用提供 GPU 图形加速，通过宿主的 `mali_kbase` 驱动访问 `/dev/mali0`。 |
| Arm allocator / mapper5 | 分配图形缓冲区，并将缓冲区导入使用它的进程。 |
| HWC（Hardware Composer）资源适配层 | 管理显示合成使用的缓冲区，将 ReDroid 的资源管理代码与厂商 mapper5 接口衔接；由项目源码编译。 |
| CIX Codec2 服务 | 向 Android 提供硬件编解码接口；H.264 编码通过宿主的 `amvx` 驱动访问 `/dev/video1`。 |

这些组件按固定版本配套。其他设备或驱动版本需要重新核对接口兼容性，不能直接套用本项目配置。

### 已验证的配套

- 实机测试使用 Orange Pi 6 Plus、ARM64 Linux，以及厂商 `mali_kbase` / `amvx` 驱动。早期测试内核为 `6.6.89-cix-redroid2`，发布版本 `6.6.89-cix-redroid` 也已与发布镜像配套验证。
- GPU 配套为 Mali 内核驱动 r53p0 / UK1.36，以及官方 Android 14 v1.0.1 镜像中的用户态驱动 r49p0。
- Android 基础层为锁定的 ReDroid Android 14 ARM64 镜像，仅支持 64 位应用。
- 已验证 EGL / OpenGL ES、Mali Vulkan 和 CIX H.264 硬件编码。具体测试方法和游戏测试范围见 [验证记录](VALIDATION.md)。

2026-10-19，使用者确认 2026-10-17 发布的内核 deb 和 ReDroid 镜像已在开发板上配套测试，Android 和游戏运行正常。此次验证复用了已有 Android 数据卷；早期空数据实例的测试结果单独记录在 [验证记录](VALIDATION.md) 中。

基础镜像和导入文件的 SHA256 见 [inputs.lock.json](../config/inputs.lock.json)，内核源码版本见 [sources.lock.json](../kernel/sources.lock.json)。锁定清单用于检查构建输入是否一致，不代表厂商对这些文件另行签名。

## 宿主与构建细节

开发板需要 Docker、Python 3 和兼容的宿主内核。内核需保留厂商硬件驱动，并支持 Binder / BinderFS（Android 进程间通信）、memfd（共享内存）和 IPv4 / IPv6 策略路由。在项目根目录运行 `python3 scripts/check-host.py` 可检查架构、设备、驱动绑定及内核配置；无法读取内核配置时，仍需手动确认所需选项。

原厂内核不保证已启用 Binder，构建 Android 镜像也无法补齐宿主内核功能。宿主检查脚本不安装内核；使用项目提供的 deb 安装内核时，会同时安装模块并注册 EFI 启动项，详见 [宿主内核说明](../kernel/README.md)。

构建镜像需要 `clang++`、GNU ARM64 链接器和 Docker。ARM64 构建机使用 `ld`，x86_64 交叉构建机使用 `aarch64-linux-gnu-ld`。安装命令和完整构建顺序见 [README](../README.md#2-拉取-redroid-镜像) 中的手动构建说明。

### 厂商文件来源

日常构建使用约 23.8 MB 的厂商资源包，包含 48 个原始文件。`download-vendor.py` 按 [vendor-bundle.lock.json](../config/vendor-bundle.lock.json) 校验整包，`import-vendor-bundle.py` 只导入允许的路径，并按逐文件清单再次核对。下载地址与构建入口见 [CI 说明](CI.md#redroid-镜像)。

需要核对资源包来源或重新提取时，从 [Orange Pi 官方下载入口](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-6-Plus.html) 或 [Google Drive Android 目录](https://drive.google.com/drive/folders/1EGJKdZ1V4Vool18J6SyG0NVudSerBD7A) 获取锁定的 `Orangepi6plus_1.0.1_android14_linux6.1.44.7z`。将文件保存到 `work/downloads/`；额外安装 `7z` 和 `debugfs` 后，在项目根目录执行：

```sh
python3 scripts/extract-vendor.py work/downloads/Orangepi6plus_1.0.1_android14_linux6.1.44.7z
python3 scripts/prepare.py --vendor-dir work/extract/vendor
```

已有提取好的官方 `vendor/` 目录时，可直接传给 `prepare.py --vendor-dir <目录>`。该目录仍须通过锁定文件的 SHA256 校验。

### 基础镜像与适配库

`prepare.py` 创建一个不启动的基础容器，读取链接所需的库和 Android 硬件服务声明文件，校验后删除临时容器。已有相同基础镜像的本地标签时，可传入 `--base-image <标签>`。

Docker 的不同存储后端可能用配置摘要（config digest）或镜像清单摘要（manifest digest）作为镜像 ID。[common.py](../scripts/common.py) 只接受锁定基础镜像对应的这两个值，并检查 ARM64 架构和镜像未声明自动创建的数据卷。镜像身份报错时，应先核对基础镜像和 Docker 存储后端。

适配库使用固定的 Android 14 头文件，以及基础镜像中的 Bionic C 库和 libc++ 链接，确保生成库适用于 Android。无需下载完整 AOSP 源码。头文件缓存位于 `work/cache/`，可用 `build-resources.py --cxx <clang++路径> --ld <ARM64链接器路径>` 指定编译工具。

[header-sources.json](../config/header-sources.json) 中的五份头文件归档按文件内容校验，以允许 tar / gzip 元信息发生变化：

1. 对每个普通文件计算 SHA256，建立“相对路径 → 文件摘要”映射。
2. 将映射按键排序，以无额外空格的 JSON 编码后计算 SHA256，与 `tree_sha256` 比较；同时核对 `regular_files` 文件数。
3. 仅将验证通过的普通文件写入头文件目录；跳过链接，拒绝越界和重复路径。新下载的归档验证成功后才进入缓存。

归档中的 `sha256` / `size` 字段记录原始压缩包信息；单独下载的 ABI（应用二进制接口）头文件直接校验文件 SHA256。校验失败时需核对文件路径和内容，不能直接用失败下载的摘要更新锁定清单。

最终本地镜像为 `orangepi6p-redroid:14`。Docker 构建上下文只包含 Dockerfile 和明确列出的待安装文件；构建通过 `COPY` 打包这些文件，不执行系统软件安装。`work/image-result.json` 记录镜像 ID，`work/payload-manifest.json` 记录安装文件及其摘要，可用于核对构建结果。

## 运行参数与数据

以下命令均在项目根目录执行。

- 默认容器名 `redroid`，1920×1080、虚拟显示 120 Hz、密度 160；ADB 仅监听 `127.0.0.1:5555`。虚拟显示 120 Hz 不代表游戏或投屏达到 120 fps。
- 可用 `run.py --width <宽> --height <高> --fps <刷新率> --dpi <密度>` 调整显示参数；完整选项见 `python3 scripts/run.py --help`。
- 运行时将项目内的 `data/<容器名>/` 绑定到 Android `/data`，保存应用和设置；驱动和配置已包含在镜像中，无需另行绑定。应用数据不打进镜像。
- `run.py` 拒绝覆盖已有容器，不会停止其他实例。已有容器使用 `docker start redroid` / `docker stop redroid`；移除容器用 `docker rm redroid`，需要保留数据时不要删除 `data/`。
- 使用 `--port 5556 --name redroid-test` 可与其他实例并存，GPU / VPU 仍是共享硬件；检查该实例时用 `python3 scripts/check-runtime.py --name redroid-test`。
- 局域网连接需显式指定 `--bind 0.0.0.0`，ADB 端口只用于可信网络。

## 可选硬件监视

```sh
sudo python3 scripts/monitor-hw.py --enable-vpu
```

GPU 指标包括驱动最近一个调频采样窗口的忙碌率、当前频率和驱动分配内存，覆盖宿主和所有容器，不能用来直接读取某个游戏的帧率。VPU 指标包括已采集会话的忙碌率与帧率。

查看 VPU 时需**先开监视，再连接 scrcpy**；会话处理超过 200 帧后才有帧率数据。已存在的会话可能漏记，因此 0% 不能直接解释为硬件空闲。

`--enable-vpu` 临时开启驱动的 debugfs 统计接口，正常退出、Ctrl+C 或收到 TERM / HUP 时恢复原值。强制终止或断电后，可能留下 `work/tmp/hw-monitor/` 恢复记录，需核对记录与当前统计开关再处理。统计的额外开销尚未量化。

## 已知限制

- 曾发生游戏重开后持续黑屏，并出现 `QueueSignalReleaseImageANDROID failed: -3`。一次容器重启后恢复，根因尚未定位。
- 实机证据仅覆盖上述固定版本组合。厂商驱动的二进制接口可能随版本变化，同为 Android 14 的组件也不保证兼容。
- H.265 编码器可枚举，但未验收实际编码；全部解码格式、持续 120 fps、长期稳定性和性能上限尚未验证。
- `androidboot.redroid_gpu_mode=guest` 配合 [gpu_config.sh](../config/gpu_config.sh) 选择 Mali 驱动。实际渲染器应以 `check-runtime.py` 输出的 Mali 状态为准。
- 不提供 GMS（Google 移动服务）、32 位 ARM 应用兼容、游戏客户端、自动登录或刷机工具。

## 源码发布与许可边界

本项目原创部分采用 MIT；AOSP 派生文件保留 Apache-2.0 及原许可证头，内核 Makefile 补丁按 GPL-2.0-only。具体文件范围和第三方声明见 [NOTICE](../NOTICE)。许可文本分别位于 [LICENSE](../LICENSE)、[Apache-2.0](../LICENSES/Apache-2.0.txt) 和 [GPL-2.0-only](../LICENSES/GPL-2.0-only.txt)。

厂商闭源二进制没有被本项目重新授权：公开源码包排除它们，构建时从厂商资源包或官方镜像导入。本地 `image.py` 只构建镜像；CNB 手动镜像流水线会将构建结果推送到当前项目的 Docker 制品库。发布镜像前需核对其中各组件的许可，镜像内 `/vendor/etc/orangepi6p-redroid/` 保留项目及上游许可声明，原厂 NOTICE 单独保留。

在项目根目录生成白名单源码包：

```sh
python3 scripts/export-source.py
```

产物 `dist/orangepi6p-redroid-source.tar.gz` 包含项目源码、配置、构建与运行脚本、文档、许可证和文件 SHA256 清单，排除 `work/`、`data/` 和内核子模块工作树。该归档不包含构建内核所需的完整厂商源码；构建内核请使用 Git 克隆并初始化子模块。验证范围和构建结果见 [验证记录](VALIDATION.md)。
