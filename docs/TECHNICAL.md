# 技术说明

日常构建、启动和连接步骤见 [README](../README.md)。本文记录版本配套、实现细节、辅助工具和验证边界。

CNB 镜像制品库、内核构建下载和 Debian 开发板使用步骤见 [CI 说明](CI.md)。内核 deb 的安装与启动项行为见 [内核说明](../kernel/README.md)。

## 实现与适用范围

Orange Pi 6 Plus / CIX P1 的 Android 14 ReDroid 适配。使用厂商 Mali EGL/Vulkan、Arm allocator/mapper5、源码构建的 HWC 资源层，以及 CIX Codec2 硬件编码。保留 ReDroid 虚拟显示，不接管宿主显示器。

这是从实机探索中整理的**固定版本最小配套**，不是通用 Mali 安装器。没有游戏、账号、ADB密钥、系统镜像、厂商 `.so` 或个人日志。原始研究工作区与正在使用的容器不属于本发布包。

### 已验证的配套

- Linux ARM64，Orange Pi 6 Plus，厂商 `mali_kbase`/`amvx`，设备 `/dev/mali0`、`/dev/video1`。
- 本机验证基线：`6.6.89-cix-redroid2`、Mali内核r53p0/UK1.36，官方Android14 v1.0.1用户态r49p0。
- 固定 ReDroid Android14 64-only ARM64 基础镜像。
- EGL/GLES、Mali Vulkan；CIX H.264 Surface硬件编码。已有实验环境实际运行《明日方舟：终末地》，用户确认音画正常、硬编码明显降低延迟。
- 派生镜像运行时只需一个 `/data` 项目目录绑定，不再依赖十几个宿主文件绑定；没有匿名volume。

版本摘要和导入文件指纹见 [inputs.lock.json](../config/inputs.lock.json)。固定指纹用于核对输入，不是独立厂商签名。

## 宿主与构建细节

先在项目根目录运行 `python3 scripts/check-host.py`。需要Docker、Python3、保留厂商硬件适配并开启Binder/BinderFS、memfd和IPv4/IPv6策略路由的内核。**普通原厂内核不保证满足Binder条件**，构建Android镜像也不能补齐宿主内核功能。参见 [宿主内核说明](../kernel/README.md)。容器构建/检查脚本不安装内核；可选内核 deb 的安装会写入内核、模块并注册 EFI 启动项。

构建需已有 `clang++`、GNU ARM64 linker（ARM64机器用`ld`，x86_64交叉构建用`aarch64-linux-gnu-ld`）、Docker。直接解析官方压缩镜像还需 `7z`、`debugfs`。这些工具的安装由使用者在自己的系统上决定。

日常构建使用约 23.8MB 的原始厂商资源包，包含 48 个文件；`download-vendor.py` 接收 URL，按 `vendor-bundle.lock.json` 固定摘要校验，`import-vendor-bundle.py` 白名单导入后仍按原始清单逐份验证。入口见 [CI 说明](CI.md)。

需要从完整官方镜像重新提取时，可从 [Orange Pi 官方下载入口](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-6-Plus.html) 或 [Google Drive Android 目录](https://drive.google.com/drive/folders/1EGJKdZ1V4Vool18J6SyG0NVudSerBD7A) 查找，文件可能受下载配额限制。将锁定的 `.7z` 放入 `work/downloads/`，执行 `python3 scripts/extract-vendor.py work/downloads/Orangepi6plus_1.0.1_android14_linux6.1.44.7z`，再用 `python3 scripts/prepare.py --vendor-dir work/extract/vendor` 导入；该原包入口保留供维护与溯源。

已有提取的官方 `vendor/` 时直接给 `--vendor-dir`，不必重复解整张镜像。`prepare.py`创建一个**不启动的**基础容器，读取链接依赖/manifest后删除；验证确切image ID及文件SHA。已有同一基础镜像的本地标签可显式传 `--base-image <tag>`，ID不同会拒绝。

源码编译仅用固定Android14头和基础镜像Bionic/libc++，不用宿主glibc/libstdc++；不是要求下载完整AOSP。头文件从上游按摘要下载至`work/cache/`。可指定 `build-resources.py --cxx <clang++> --ld <ARM64-GNU-ld>`；x86_64交叉构建和ARM64 Docker构建可分开，复制本地产生的`work/rootfs/`到目标板后运行`image.py`即可。

最终本地镜像为 `orangepi6p-redroid:14`。Docker构建上下文只包含Dockerfile和明确列出的生成payload；`work/image-result.json`记录ID，`work/payload-manifest.json`记录每个安装文件。构建只使用COPY，无系统软件安装步骤。

## 运行参数与数据

以下命令均在项目根目录执行。

- 默认容器名 `redroid`，1920×1080、虚拟显示 120Hz、密度 160；ADB 仅监听 `127.0.0.1:5555`。虚拟显示 120Hz 不代表游戏或投屏达到 120fps。
- 可用 `run.py --width <宽> --height <高> --fps <刷新率> --dpi <密度>` 调整显示参数；完整选项见 `python3 scripts/run.py --help`。
- 运行时只绑定项目内的 `data/<容器名>/` 到 `/data`，没有匿名 volume，也无需十几个宿主文件绑定。应用数据不打进镜像。
- `run.py` 拒绝覆盖已有容器，不会停止其他实例。已有容器使用 `docker start redroid` / `docker stop redroid`；移除容器用 `docker rm redroid`，需要保留数据时不要删除 `data/`。
- 使用 `--port 5556 --name redroid-test` 可与其他实例并存，GPU / VPU 仍是共享硬件；检查该实例时用 `python3 scripts/check-runtime.py --name redroid-test`。
- 局域网连接需显式指定 `--bind 0.0.0.0`，ADB 端口只用于可信网络。

## 可选硬件监视

```sh
sudo python3 scripts/monitor-hw.py --enable-vpu
```

GPU显示最近DVFS窗口忙碌率/频率/驱动内存，VPU显示已采集会话忙碌率与编码FPS。VPU需**先开监视，再连接scrcpy**，超过200帧后才有FPS。已有会话可能漏记，0%不自动代表空闲。该显式选项临时开启debugfs统计，Ctrl+C或TERM/HUP退出恢复原值；SIGKILL/断电可能留下`work/tmp/hw-monitor/`恢复记录。统计会增加驱动工作，额外开销未量化。

## 已知限制

- 曾发生游戏重开后持续黑屏、`QueueSignalReleaseImageANDROID failed: -3`；单次容器重启恢复，后续重开也成功过。**根因未定位，未宣称修复**。
- 只有固定基础镜像/官方vendor/宿主驱动组合有实机证据；不能因都叫Android14就随意混用私有ABI。
- H.265编码器可枚举但未验收实际编码；全部解码格式、120fps、长稳和性能排名未验证。
- 镜像内`androidboot.redroid_gpu_mode=guest`是为了绕过上游Mesa/DRM选择器，实际`gpu_config.sh`明确选择Mali；不能只看这个启动参数判断软件渲染。
- 不包含GMS、ARM32兼容、游戏客户端、自动登录或刷机工具。

## 源码发布与许可边界

本项目原创部分采用 MIT；AOSP 派生文件保留 Apache-2.0 及原许可证头，内核 Makefile 补丁按 GPL-2.0-only。具体文件范围和第三方声明见 [NOTICE](../NOTICE)。许可文本分别位于 [LICENSE](../LICENSE)、[Apache-2.0](../LICENSES/Apache-2.0.txt) 和 [GPL-2.0-only](../LICENSES/GPL-2.0-only.txt)。

厂商闭源二进制没有被本项目重新授权：公开源码包排除它们，构建时从官方镜像导入。本地 `image.py` 只构建镜像；CNB 手动镜像流水线会将构建结果推送到当前项目的 Docker 制品库。发布镜像前需核对其中各组件的许可，镜像内 `/vendor/etc/orangepi6p-redroid/` 保留项目及上游许可声明，原厂 NOTICE 仍单独保留。

在项目根目录生成白名单源码包：

```sh
python3 scripts/export-source.py
```

产物 `dist/orangepi6p-redroid-source.tar.gz` 只含源码、配置、构建/运行入口、文档、许可证和 SHA 清单；不含 `work/`、`data/`、密钥或研究历史。验证范围和构建结果见 [验证记录](VALIDATION.md)。
