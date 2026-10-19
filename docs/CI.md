# CNB 构建与发布

[.cnb.yml](../.cnb.yml) 提供两个手动流水线：**构建 ReDroid 镜像**、**构建内核 deb**。按钮配置见 [.cnb/web_trigger.yml](../.cnb/web_trigger.yml)。本项目使用 CNB 执行构建并保存产物，GitHub 源码镜像不提供构建入口。

触发这些手动构建需要仓库写权限，公开仓库的普通读者不能直接在主仓库运行。若要自行构建，请先在 CNB Fork，再到自己的仓库触发；只使用已发布的内核和镜像无需 Fork。权限依据见 [CNB 手动触发权限说明](https://docs.cnb.cool/zh/build/web-trigger.md#权限说明)。

## 如何使用

1. 登录 CNB，将 [CNB 主仓库](https://cnb.cool/li_chx/redroid-orangepi6p) Fork 到自己的组织。
2. 打开自己 Fork 仓库的 **main 分支详情页**，选择需要的构建按钮。ReDroid 需要填 Android 14 厂商资源包的公开 HTTPS 直链；内核构建不需要这个文件。
3. ReDroid 构建完成后，在自己的仓库中通过 **制品库 → Docker → redroid** 查看镜像；内核构建结果在自己仓库中触发构建的提交附件里，文件名 `kernel-<构建ID>.tar`，保留 7 天。

已发布的内核可直接下载 [固定版本包](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases/download/kernel-6.6.89-cix-redroid-20261017/kernel-cnb-u9c-1k53v2noi.tar)，无需自行运行 CI；[Release 列表](https://cnb.cool/li_chx/redroid-orangepi6p/-/releases)长期保存该包及外层校验文件。包内安装方式见 [内核说明](../kernel/README.md#安装与启动项)。

两条流水线按需独立运行，不在普通 push 或 PR 时自动构建，也不连接开发板。ReDroid 使用 ARM64 节点，内核在 amd64 节点上使用固定的 Arm GCC 12.3 工具链交叉编译。依赖预装在 [.ci/](../.ci/) 的构建环境 Dockerfile 中，CNB 可缓存这些环境。

配置格式、按钮和发布参数依据 [CNB 手动触发文档](https://docs.cnb.cool/zh/build/web-trigger.md)、[Docker 制品库说明](https://docs.cnb.cool/zh/artifact/docker.html)、[构建节点说明](https://docs.cnb.cool/zh/build/build-node.md) 及 [官方附件插件](https://cnb.cool/cnb/plugins/cnbcool/attachments)。

## ReDroid 镜像

在按钮表单的 `VENDOR_ARCHIVE_URL` 中填写 `orangepi6p-android14-vendor-1.0.1.tar.gz` 资源包的 HTTPS 下载直链：

```text
https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor/-/releases/download/1.0/orangepi6p-android14-vendor-1.0.1.tar.gz
```

资源包约 23.8 MB，包含构建所需的 48 份原厂驱动、配置等文件及来源声明，无需下载完整官方刷机镜像。该 Release 的 [SHA256 文件](https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor/-/releases/download/1.0/orangepi6p-android14-vendor-1.0.1.tar.gz.sha256) 供手动核对；CI 使用 [vendor-bundle.lock.json](../config/vendor-bundle.lock.json) 中固定的 SHA256 校验下载内容，表单只需填写压缩包链接。

流水线依次执行：

1. 运行资源包导入、头文件校验和基础镜像兼容性测试。
2. 下载资源包，校验整个归档及包内文件；只导入允许的路径，并按 [inputs.lock.json](../config/inputs.lock.json) 核对每个文件的 SHA256。
3. 运行 `prepare.py` 整理厂商文件和基础镜像依赖，下载头文件，编译适配库并构建镜像。
4. 将镜像推送到当前仓库的 Docker 制品库。

导入的厂商文件位于 `work/vendor-input/`。URL 可以替换为提供相同内容的镜像地址；若改用其他版本的资源包，必须先核对兼容性并更新锁定清单，内容不匹配时构建会停止。

表单不是密钥存储，含签名或凭据的 URL 应放入 [CNB 密钥仓库](https://docs.cnb.cool/zh/repo/secret.md)，并在 `.cnb.yml` 的 ReDroid Pipeline 中通过 `imports` 导入 `VENDOR_ARCHIVE_URL`；同时移除按钮中的必填 URL 输入。下载脚本不会主动打印 URL，产物也不记录 URL。

流水线使用 CNB 临时构建凭据，将已构建镜像推送到：

```text
${CNB_DOCKER_REGISTRY}/${CNB_REPO_SLUG_LOWERCASE}/redroid:14
${CNB_DOCKER_REGISTRY}/${CNB_REPO_SLUG_LOWERCASE}/redroid:build-${CNB_BUILD_ID}
```

`14` 表示 Android 14，随每次成功的手动构建更新；`build-<构建ID>` 用于选定某次构建。镜像通过 Docker 制品库分发。源码提交记录在镜像的 `org.opencontainers.image.revision` 标签中，许可文件位于镜像内 `/vendor/etc/orangepi6p-redroid/`。

本仓库的 ARM64 镜像地址为 `docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:14`。2026-10-17 发布的固定版本使用 `build-cnb-9rb-1k53vpcv5` 标签，对应提交 `52c099f`。

在 Debian ARM64 开发板克隆本项目源码，然后拉取镜像。下面给出本项目实际地址；自己的 Fork 应改用自己的项目路径：

```sh
git clone https://cnb.cool/li_chx/redroid-orangepi6p.git orangepi6p-redroid
cd orangepi6p-redroid
docker pull docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:14
python3 scripts/check-host.py
python3 scripts/run.py --image docker.cnb.cool/li_chx/redroid-orangepi6p/redroid:14
python3 scripts/check-runtime.py
```

开发板需事先安装 Git、Docker、Python 3，并满足 [宿主内核前提](../kernel/README.md)。连接和应用数据位置见 [README](../README.md)。

<details>
<summary>使用自己的私有 Fork</summary>

若自己的 Fork 设为私有，需使用有仓库访问权限的 Git 凭据；拉取该 Fork 的镜像前，使用 `docker login docker.cnb.cool --username cnb` 登录，密码输入具有制品读取权限的 CNB 令牌。

</details>

镜像包含厂商组件和 ReDroid 基础层，各自沿用原许可，发布前应核对再分发条件。只发布源码时可使用 `scripts/export-source.py`，它排除厂商二进制与生成目录。详见 [NOTICE](../NOTICE)。

## 内核 deb

内核流水线固定生成 **`6.6.89-cix-redroid`**，包含内核自带模块、六个厂商外置模块和本板的设备树文件（DTB）。构建时检查 ARM64 架构、模块版本标记（vermagic）、Mali 模块依赖顺序和 deb 内的实际文件，并将对应的内核、驱动源码与最终配置一起打包。

Linux 与厂商驱动源码由 Git 子模块 `kernel/vendor-snapshot/` 提供，来源为 [CNB vendor 仓库](https://cnb.cool/li_chx/Orangepi6plus-redroid-vendor)。子模块路径见 [.gitmodules](../.gitmodules)，固定提交、上游来源和目录内容标识见 [sources.lock.json](../kernel/sources.lock.json)。构建会校验这些信息，确保使用指定版本的源码。

内核任务设置 `git.submodules: { enable: true, remote: false }`，由 CNB 在准备阶段检出固定子模块提交，不跟踪分支最新版本；ReDroid 镜像任务不需要内核源码，因此关闭子模块。源码从 CNB 下载，Arm 编译器按锁定 URL 单独下载并校验 SHA256。子模块行为见 [CNB Git 配置](https://docs.cnb.cool/zh/build/grammar.html#git)。

对应源码包只收录已打补丁的 Linux 和锁定清单中的四个公开驱动目录，附带 vendor 快照来源清单，排除其他源码和 Git 元数据；项目源码包保留 `.gitmodules`，排除整个 `kernel/vendor-snapshot/` 和 `kernel/work/`。本地构建入口见 [内核 README](../kernel/README.md)。

在开发板上解开外层 TAR 后执行：

```sh
sha256sum -c SHA256SUMS
sudo apt install ./linux-image-6.6.89-cix-redroid_*_arm64.deb
```

安装成功时会自动注册 EFI GRUB 启动项并设为默认，保留原厂 `/Image` 和原厂菜单；不会自动重启。ESP 选择、支持的 Debian 布局、恢复方式和完整源码说明见 [内核 README](../kernel/README.md)。

CI 的编译与打包检查不代替开发板启动、GPU / VPU 或游戏测试。2026-10-17 发布的内核与镜像已由使用者在开发板上配套验证，复用已有 Android 数据卷，测试和游戏运行正常。具体测试范围见 [验证记录](VALIDATION.md)。
