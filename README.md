# Orange Pi 6 Plus ReDroid GPU / VPU

## 这是什么

在 **Orange Pi 6 Plus（CIX P1）** 上运行 Android 14 容器的适配项目，支持 Mali GPU 图形加速、Vulkan 和 CIX H.264 硬件编码，可通过 ADB / scrcpy 连接、投屏和操作 Android 应用。

Android 使用虚拟显示，不接管开发板的宿主桌面。当前仅验证固定的 ReDroid、官方 Android 驱动和宿主内核组合；源码仓库不包含 Android 系统镜像、厂商驱动二进制、GMS 或应用安装包。

本项目的 CI、内核 Release 和 Docker 镜像统一由 [CNB 主仓库](https://cnb.cool/li_chx/redroid-orangepi6p)提供。源码同步到 GitHub 后，仍使用下方的 CNB 构建和下载入口，无需在 GitHub 配置 CI。

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

1. 打开 [CNB 主仓库](https://cnb.cool/li_chx/redroid-orangepi6p)（或自己的 CNB Fork）的 **main 分支详情页**，点击 **构建内核 deb**；无需填写 Android 资源包地址。
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

### 2. 拉取 ReDroid 镜像

在开发板上安装 Git、Docker 和 Python 3，克隆本项目取得启动与检查脚本（无需递归拉取内核快照）：

```sh
git clone https://cnb.cool/li_chx/redroid-orangepi6p.git
cd redroid-orangepi6p
```

拉取预构建的 ARM64 镜像：

```sh
docker pull docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:14
```

`14` 会随成功构建更新。需要固定本次发布的镜像时，使用 `docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:build-cnb-9rb-1k53vpcv5`；镜像平台为 `linux/arm64`。

<details>
<summary>自行使用 CNB CI 构建镜像</summary>

1. 打开 [CNB 主仓库](https://cnb.cool/li_chx/redroid-orangepi6p)（或自己的 CNB Fork）的 **main 分支详情页**，点击 **构建 ReDroid 镜像**。
2. 在 `VENDOR_ARCHIVE_URL` 中填写下面的公开资源包直链：

   ```text
   https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor/-/releases/download/1.0/orangepi6p-android14-vendor-1.0.1.tar.gz
   ```

3. 构建成功后，在所用 CNB 项目的 **制品库 → Docker → redroid** 获取镜像地址。自己的 CNB Fork 应把 `your-org/your-repo` 替换为实际组织与仓库路径：

   ```sh
   docker pull docker.cnb.cool/your-org/your-repo/redroid:14
   ```

CI 在 ARM64 节点运行，自动校验固定资源包、编译适配库并推送 `14` 和 `build-<构建ID>` 两个标签。无需先在 CI 构建内核；开发板运行时仍需满足宿主内核要求。详细配置见 [CI 文档](docs/CI.md#redroid-镜像)。

</details>

<details>
<summary>手动构建镜像：Debian / Ubuntu ARM64 + Docker</summary>

在 ARM64 Linux 上准备 Docker、Python 3、Clang 和 GNU linker。使用项目 Git 工作树，不需要初始化内核 submodule：

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  ca-certificates git python3 clang binutils gzip tar
```

Docker 需已安装、服务可用，且当前用户能执行 `docker info`。然后下载并校验约 23.8 MB 的固定厂商资源包，导入资源，编译适配库并构建本地镜像：

```sh
export VENDOR_ARCHIVE_URL='https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor/-/releases/download/1.0/orangepi6p-android14-vendor-1.0.1.tar.gz'
python3 scripts/download-vendor.py
python3 scripts/import-vendor-bundle.py
python3 scripts/prepare.py --vendor-dir work/vendor-input
python3 scripts/fetch-headers.py
python3 scripts/build-resources.py
python3 scripts/image.py
```

完成后得到本地镜像 `orangepi6p-redroid:14`。使用它启动时，将下一节的 `--image` 参数改为 `orangepi6p-redroid:14`。下载、解包和编译中间文件位于 `work/`，无需下载完整官方刷机镜像；固定资源包的校验值见 [锁定清单](config/vendor-bundle.lock.json)。

<details>
<summary>在 x86_64 Linux 构建，或推送到自己的制品库</summary>

x86_64 Debian / Ubuntu 还需安装 ARM64 GNU linker，并确保 Docker 能拉取、创建和导出 ARM64 基础镜像：

```sh
sudo apt-get install binutils-aarch64-linux-gnu
```

`build-resources.py` 自动使用 `aarch64-linux-gnu-ld`；其余步骤与上面相同。当前构建脚本通过导出基础镜像和无 `RUN` 指令的 Dockerfile 打包，无需启动 Android 容器。实际运行与验证仍在开发板上完成。

如需发布到自己有写权限的 CNB 项目，构建完成后将 `your-org/your-repo` 替换为目标项目路径并执行：

```sh
docker login docker.cnb.cool --username cnb
docker tag orangepi6p-redroid:14 docker.cnb.cool/your-org/your-repo/redroid:14
docker push docker.cnb.cool/your-org/your-repo/redroid:14
```

</details>
</details>

### 3. 启动并连接

在开发板的项目根目录，检查宿主条件并准备持久化数据目录。`gpu-mapper5-stats` 是适配库的统计目录，需要允许 Android 的 UID / GID `1000:1000` 写入：

```sh
python3 scripts/check-host.py
mkdir -p data/redroid/gpu-mapper5-stats
sudo chown 1000:1000 data/redroid/gpu-mapper5-stats
sudo chmod 700 data/redroid/gpu-mapper5-stats
```

使用原始 Docker 命令启动 Android：

```sh
docker run -d \
  --name redroid \
  --privileged \
  --restart=no \
  --pull=never \
  --mount "type=bind,src=$PWD/data/redroid,dst=/data" \
  -p 127.0.0.1:5555:5555 \
  docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:14 \
  androidboot.use_memfd=1 \
  androidboot.redroid_gpu_mode=guest \
  androidboot.redroid_width=1920 \
  androidboot.redroid_height=1080 \
  androidboot.redroid_fps=120 \
  androidboot.redroid_dpi=160

python3 scripts/check-runtime.py
```

<details>
<summary>启动参数说明</summary>

Docker 参数位于镜像名之前，Android 启动参数位于镜像名之后。

| 参数 | 作用 |
| --- | --- |
| `-d` | 在后台运行容器。 |
| `--name redroid` | 容器名，供后续 `docker start`、`docker stop`、检查脚本使用。 |
| `--privileged` | 授予扩展权限并开放宿主设备，供当前 Android 容器方案访问 Binder、Mali 和 VPU 等设备。 |
| `--restart=no` | 不随容器退出或 Docker 重启自动启动；需要时执行 `docker start redroid`。 |
| `--pull=never` | 使用本地镜像，需要先完成上文的 `docker pull`。 |
| `--mount ...` | 将项目内的 `data/redroid/` 绑定到 Android `/data`，保存应用和设置；`$PWD` 应是项目根目录。 |
| `-p 127.0.0.1:5555:5555` | 将宿主本机的 TCP 5555 映射到容器 ADB 的 TCP 5555。左侧地址 / 端口控制宿主监听，右侧是容器端口。 |
| `androidboot.use_memfd=1` | 使用 memfd 作为共享内存后端。 |
| `androidboot.redroid_gpu_mode=guest` | 使用容器内的图形驱动；本镜像已配套 Mali EGL / Vulkan 和 Arm allocator / mapper。 |
| `androidboot.redroid_width=1920`、`androidboot.redroid_height=1080` | Android 虚拟显示的宽、高，单位为像素。 |
| `androidboot.redroid_fps=120` | 虚拟显示目标刷新率；本项目还会同步 Android 刷新率策略。实际应用和投屏帧率取决于负载及编码设置。 |
| `androidboot.redroid_dpi=160` | Android 显示密度，影响界面缩放。 |

例如将宽、高改为 `1280`、`720`，并将 FPS 改为 `60`，即可请求 1280×720、60 Hz 的虚拟显示。Docker 选项详见 [官方 docker run 文档](https://docs.docker.com/reference/cli/docker/container/run/)，Android 参数见 [ReDroid 文档](https://github.com/remote-android/redroid-doc)。

</details>

<details>
<summary>也可使用项目启动脚本</summary>

下面的命令自动检查宿主、准备上述目录，并使用与原始 Docker 命令相同的默认参数启动。两种方式选择一种即可，避免重复创建同名容器：

```sh
python3 scripts/run.py --image docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:14
python3 scripts/check-runtime.py
```

修改显示参数可传入 `--width`、`--height`、`--fps`、`--dpi`；修改容器名时，检查脚本也需传入相同的 `--name`，并会改用 `data/<容器名>/` 目录。

</details>

连接端需安装 ADB 和 scrcpy。默认容器名 `redroid`，显示为 1920×1080，ADB 地址为 `127.0.0.1:5555`。在开发板本机连接：

```sh
adb connect 127.0.0.1:5555
scrcpy -s 127.0.0.1:5555 --video-encoder=c2.cix.avc.encoder -b 32M --max-fps=60
```

若从另一台电脑连接，在创建容器时把原始命令中的端口映射改为 `-p 0.0.0.0:5555:5555`；使用项目脚本时追加 `--bind 0.0.0.0 --port 5555`。仅在可信局域网开放 ADB，连接端将 `127.0.0.1` 换成开发板 IP。已有容器的端口映射不能通过 `docker start` 修改。

应用数据保存在 `data/redroid/`。已有容器用 `docker start redroid` 启动、`docker stop redroid` 停止，无需重复运行 `run.py`。保留应用数据时不要删除该目录。

实现原理、版本配套、硬件监视及已知问题见 [技术说明](docs/TECHNICAL.md)，实测范围见 [验证记录](docs/VALIDATION.md)。

## 非 AI 留言

这个项目的实现比我想的简单很多，一方面得益于驱动和内核的实现确实足够完善，但另一方面也得益于 AI 的强大。我原本预计需要我和 AI 合作实现 Android 的图形转译层，但官方镜像中已有的驱动能做到拿来即用，最终实现上没有什么阻碍。

## 许可证

本项目原创部分采用 [MIT](LICENSE)；AOSP 派生源码保留 Apache-2.0，内核补丁保留 GPL-2.0-only，厂商文件沿用原许可。各部分的适用范围见 [NOTICE](NOTICE)。
