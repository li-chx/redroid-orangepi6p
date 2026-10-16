# Orange Pi 6 Plus ReDroid GPU / VPU

## 这是什么

在 **Orange Pi 6 Plus（CIX P1）** 上运行 Android 14 容器的适配项目，支持 Mali GPU 图形加速、Vulkan 和 CIX H.264 硬件编码，可通过 ADB / scrcpy 连接、投屏和操作 Android 应用。

Android 使用虚拟显示，不接管开发板的宿主桌面。当前仅验证固定的 ReDroid、官方 Android 驱动和宿主内核组合；源码仓库不包含 Android 系统镜像、厂商驱动二进制、GMS 或应用安装包。

## 怎么用

### 1. 准备开发板

开发板需要保留厂商 GPU / VPU 驱动，并具备 Binder 等 Android 容器所需的内核功能；普通原厂内核不保证可用。先按 [宿主内核说明](kernel/README.md) 检查，再在项目目录执行：

```sh
python3 scripts/check-host.py
```

构建需要 Docker、Python 3、`clang++`、GNU ARM64 linker（板上为 `ld`）；解包官方镜像还需 `7z`、`debugfs`。连接端需要 ADB 和 scrcpy。

### 2. 构建镜像

也可使用 [CNB 流水线构建并推送到项目制品库](docs/CI.md)，在开发板上拉取使用；以下为本地构建方式。

下载 [Android 14 厂商资源包](https://cnb.cool/li_chx/Orangepi6plus-redroid-android-vendor/-/releases/download/1.0/orangepi6p-android14-vendor-1.0.1.tar.gz)（约 23.8MB），放入 `work/downloads/`，然后执行：

```sh
python3 scripts/import-vendor-bundle.py
python3 scripts/prepare.py --vendor-dir work/vendor-input
python3 scripts/fetch-headers.py
python3 scripts/build-resources.py
python3 scripts/image.py
```

完成后得到本地镜像 `orangepi6p-redroid:14`。

### 3. 启动并连接

在开发板上启动并检查 Android：

```sh
python3 scripts/run.py
python3 scripts/check-runtime.py
```

默认容器名 `redroid`，显示为 1920×1080，ADB 地址为 `127.0.0.1:5555`。在开发板本机连接：

```sh
adb connect 127.0.0.1:5555
scrcpy -s 127.0.0.1:5555 --video-encoder=c2.cix.avc.encoder -b 32M --max-fps=60
```

若从另一台电脑连接，启动时将上面的 `run.py` 命令换成下列命令，仅在可信局域网使用；连接端将 `127.0.0.1` 换成开发板 IP：

```sh
python3 scripts/run.py --bind 0.0.0.0 --port 5555
```

应用数据保存在 `data/redroid/`。已有容器用 `docker start redroid` 启动、`docker stop redroid` 停止，无需重复运行 `run.py`。保留应用数据时不要删除该目录。

实现原理、版本配套、硬件监视及已知问题见 [技术说明](docs/TECHNICAL.md)，实测范围见 [验证记录](docs/VALIDATION.md)。

## 许可证

本项目原创部分采用 [MIT](LICENSE)；AOSP 派生源码保留 Apache-2.0，内核补丁保留 GPL-2.0-only，厂商文件沿用原许可。各部分的适用范围见 [NOTICE](NOTICE)。
