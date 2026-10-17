# Orange Pi 6 Plus ReDroid GPU / VPU

## 这是什么

在 **Orange Pi 6 Plus（CIX P1）** 上运行 Android 14 容器的适配项目，支持 Mali GPU 图形加速、Vulkan 和 CIX H.264 硬件编码，可通过 ADB / scrcpy 连接、投屏和操作 Android 应用。

Android 使用虚拟显示，不接管开发板的宿主桌面。当前仅验证固定的 ReDroid、官方 Android 驱动和宿主内核组合；源码仓库不包含 Android 系统镜像、厂商驱动二进制、GMS 或应用安装包。

## 怎么用

### 1. 下载并安装宿主内核

适用于 Orange Pi 6 Plus 官方 Debian ARM64 系统，内核版本为 **`6.6.89-cix-redroid`**，包含 Binder 和配套 GPU / NPU / VPU / ISP 模块。已有兼容内核可跳过安装，直接进行宿主检查。

下载 [内核发布包](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases/download/kernel-6.6.89-cix-redroid-20261017/kernel-cnb-u9c-1k53v2noi.tar)（约 224 MB）和 [外层 SHA256 文件](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases/download/kernel-6.6.89-cix-redroid-20261017/kernel-cnb-u9c-1k53v2noi.tar.sha256)；历史版本见 [Release 列表](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases)。包内包含 ARM64 deb、对应内核与驱动源码、最终配置和校验清单。在开发板上执行：

```sh
sha256sum -c kernel-cnb-u9c-1k53v2noi.tar.sha256
mkdir kernel-release
tar -xf kernel-cnb-u9c-1k53v2noi.tar -C kernel-release
cd kernel-release
sha256sum -c SHA256SUMS
sudo apt install ./linux-image-6.6.89-cix-redroid_*_arm64.deb
```

安装成功后会添加并默认选中新内核的 EFI GRUB 启动项，保留原厂入口。**安装不会自动重启**；确认安装成功后执行 `sudo reboot`，再用 `uname -r` 核对版本。自动注册要求官方 ACPI、无 initrd、同盘 EFI 分区布局，其他布局和恢复方法见 [宿主内核说明](kernel/README.md#安装与启动项)。

<details>
<summary>自行使用 CNB CI 构建内核</summary>

1. 打开本仓库或自己的 CNB Fork 的 **main 分支详情页**，点击 **构建内核 deb**；无需填写 Android 资源包地址。
2. 等待测试、内核和六个厂商模块编译、打包及上传全部成功。
3. 在触发构建的提交附件中下载 `kernel-<构建ID>.tar`，按上面的步骤校验并安装。CI 提交附件保留 **7 天**，需要长期保存时另行上传到 Release。

任务运行在 amd64 节点，不依赖云原生开发工作区，也不会连接或修改开发板。配置见 [.cnb.yml](.cnb.yml)，更多说明见 [CI 文档](docs/CI.md#内核-deb)。

</details>

<details>
<summary>手动构建内核：x86_64 Linux + Docker</summary>

需要 Git、Docker 和能访问 CNB / Arm 工具链下载地址的网络；输出为 ARM64 内核包。请使用 Git 克隆，项目源码压缩包不包含内核快照。

```sh
git clone https://cnb.cool/li_chx/redroid-orangepi6p.git
cd redroid-orangepi6p
git submodule update --init --recursive
docker build -f .ci/kernel.Dockerfile -t orangepi6p-kernel-builder .
docker run --rm -e JOBS=8 \
  -v "$PWD:/workspace" -w /workspace \
  orangepi6p-kernel-builder bash -ec \
  'git config --global --add safe.directory /workspace; git config --global --add safe.directory /workspace/kernel/vendor-snapshot; python3 kernel/tests/test_kernel.py && bash kernel/build.sh'
```

`JOBS` 控制并行数，请按机器资源调整。产物在 `dist/kernel/`，日志与编译缓存位于 `kernel/work/`；Docker 默认以 root 写入挂载目录。安装时将 `dist/kernel/` 中的文件一起复制到开发板，先校验 `SHA256SUMS`，再安装 deb。

<details>
<summary>不使用 Docker：Debian / Ubuntu x86_64 宿主依赖和入口</summary>

在上述 Git 工作树中安装依赖，初始化固定快照，然后运行同一构建入口：

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  ca-certificates git python3 build-essential bc bison flex libssl-dev libelf-dev \
  libncurses-dev kmod file cpio rsync tar xz-utils dpkg-dev grub-common
git submodule update --init --recursive
python3 kernel/tests/test_kernel.py
JOBS=8 bash kernel/build.sh
```

构建脚本会下载并校验固定的 Arm GNU 交叉工具链、应用内核补丁并打包对应源码。源码版本、补丁和打包范围见 [内核构建说明](kernel/README.md#源码与配套边界)。

</details>
</details>

### 2. 构建镜像

也可使用 [CNB 流水线构建并推送到项目制品库](docs/CI.md)，在开发板上拉取使用；以下为本地构建方式。

下载 [Android 14 厂商资源包](https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor/-/releases/download/1.0/orangepi6p-android14-vendor-1.0.1.tar.gz)（约 23.8MB），放入 `work/downloads/`，然后执行：

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
