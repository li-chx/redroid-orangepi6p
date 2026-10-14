# Orange Pi 6 Plus ReDroid GPU / VPU

Orange Pi 6 Plus / CIX P1 的 Android 14 ReDroid 适配。使用厂商 Mali EGL/Vulkan、Arm allocator/mapper5、源码构建的 HWC 资源层，以及 CIX Codec2 硬件编码。保留 ReDroid 虚拟显示，不接管宿主显示器。

这是从实机探索中整理的**固定版本最小配套**，不是通用 Mali 安装器。没有游戏、账号、ADB密钥、系统镜像、厂商 `.so` 或个人日志。原始研究工作区与正在使用的容器不属于本发布包。

## 已支持的范围

- Linux ARM64，Orange Pi 6 Plus，厂商 `mali_kbase`/`amvx`，设备 `/dev/mali0`、`/dev/video1`。
- 本机验证基线：`6.6.89-cix-redroid2`、Mali内核r53p0/UK1.36，官方Android14 v1.0.1用户态r49p0。
- 固定 ReDroid Android14 64-only ARM64 基础镜像；版本摘要和所有导入文件SHA256见 `config/inputs.lock.json`。
- EGL/GLES、Mali Vulkan；CIX H.264 Surface硬件编码。已有实验环境实际运行《明日方舟：终末地》，用户确认音画正常、硬编码明显降低延迟。
- 派生镜像运行时只需一个 `/data` 项目目录绑定，不再依赖十几个宿主文件绑定；没有匿名volume。

## 宿主前提

先运行 `python3 scripts/check-host.py`。需要Docker、Python3、保留厂商硬件适配并开启Binder/BinderFS、memfd和IPv4/IPv6策略路由的内核。**普通原厂内核不保证满足Binder条件**，构建Android镜像也不能补齐宿主内核功能。参见 [kernel/README.md](kernel/README.md)。脚本不安装内核、不修改 `/boot`、模块、固件或启动配置。

构建需已有 `clang++`、GNU ARM64 linker（ARM64机器用`ld`，x86_64交叉构建用`aarch64-linux-gnu-ld`）、Docker。直接解析官方压缩镜像还需 `7z`、`debugfs`。这些工具的安装由使用者在自己的系统上决定。

## 构建

1. 自行从 [Orange Pi 官方下载入口](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-6-Plus.html) 获取 `Orangepi6plus_1.0.1_android14_linux6.1.44.7z`，存入本目录的`work/downloads/`。官方页面对应的 [Google Drive Android目录](https://drive.google.com/drive/folders/1EGJKdZ1V4Vool18J6SyG0NVudSerBD7A) 可作为入口；文件可能受下载配额限制。`inputs.lock.json`记录本机使用文件的指纹，不把它称为独立厂商签名。
2. 在项目目录中执行：

```sh
python3 scripts/extract-vendor.py work/downloads/Orangepi6plus_1.0.1_android14_linux6.1.44.7z
python3 scripts/prepare.py --vendor-dir work/extract/vendor
python3 scripts/fetch-headers.py
python3 scripts/build-resources.py
python3 scripts/image.py
```

已有提取的官方 `vendor/` 时直接给 `--vendor-dir`，不必重复解整张镜像。`prepare.py`创建一个**不启动的**基础容器，读取链接依赖/manifest后删除；验证确切image ID及文件SHA。已有同一基础镜像的本地标签可显式传 `--base-image <tag>`，ID不同会拒绝。

源码编译仅用固定Android14头和基础镜像Bionic/libc++，不用宿主glibc/libstdc++；不是要求下载完整AOSP。头文件从上游按摘要下载至`work/cache/`。可指定 `build-resources.py --cxx <clang++> --ld <ARM64-GNU-ld>`；x86_64交叉构建和ARM64 Docker构建可分开，复制本地产生的`work/rootfs/`到目标板后运行`image.py`即可。

最终本地镜像为 `orangepi6p-redroid:14-gpu-vpu`。Docker构建上下文只包含Dockerfile和明确列出的生成payload；`work/image-result.json`记录ID，`work/payload-manifest.json`记录每个安装文件。构建只使用COPY，无系统软件安装步骤。

## 运行和连接

```sh
python3 scripts/run.py
python3 scripts/check-runtime.py
```

默认名称`redroid`、1920×1080、虚拟显示120Hz、密度160，ADB只监听`127.0.0.1:5555`。应用持久化数据为当前项目的`data/redroid/`，重建容器不需要把数据打进镜像。脚本拒绝覆盖已有容器，不会停止其他实例。虚拟显示120Hz不代表游戏或投屏达到120fps。

需要局域网连接时明确指定：

```sh
python3 scripts/run.py --name redroid --bind 0.0.0.0 --port 5555
```

ADB端口仅用于可信网络。另一台电脑使用：

```sh
adb connect <开发板IP>:5555
scrcpy -s <开发板IP>:5555 --video-encoder=c2.cix.avc.encoder -b 32M --max-fps=60
```

`--port 5556 --name redroid-test`可与其他实例并存，但GPU/VPU仍是共享硬件。已有容器用 `docker start redroid`；停止用 `docker stop redroid`，移除容器用 `docker rm redroid`，都不要删除仍需使用的`data/`。

## 可选监视

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

## 发布边界

本仓库新增脚本和适配代码采用Apache-2.0；AOSP派生文件保留原许可证头，内核Makefile补丁按GPL-2.0-only。详见 [NOTICE](NOTICE)。厂商闭源二进制**没有被本项目重新授权**：在未核实其再分发条件前，公开源码包排除它们，使用者本地从官方镜像导入。包含这些文件的本地Docker镜像也不会由脚本自动推送。

生成白名单源码包：

```sh
python3 scripts/export-source.py
```

产物`dist/orangepi6p-redroid-source.tar.gz`只含源码、配置、构建/运行入口、文档、许可证和SHA清单；不含`work/`、`data/`、密钥或研究历史。验证范围和构建结果见 [docs/VALIDATION.md](docs/VALIDATION.md)。
