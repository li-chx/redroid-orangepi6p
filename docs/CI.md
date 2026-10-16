# CNB 构建与发布

[.cnb.yml](../.cnb.yml) 提供两个手动流水线：**构建 ReDroid 镜像**、**构建内核 deb**。按钮配置见 [.cnb/web_trigger.yml](../.cnb/web_trigger.yml)，原 GitHub Actions 工作流已移除。

## 如何使用

1. 将本仓库上传至 CNB，打开分支页面的手动构建入口。
2. 选择需要的构建按钮。ReDroid 需要填官方 Android 镜像的公开 HTTPS 直链；内核构建不需要这个文件。
3. ReDroid 构建完成后，在项目的 **制品库 → Docker → redroid** 查看镜像；内核构建结果仍在当前提交的附件中，文件名 `kernel-<构建ID>.tar`，保留 7 天。

两条流水线按需独立运行，不在普通 push 或 PR 时自动构建，也不连接开发板。ReDroid 使用 ARM64 节点，内核在 amd64 节点上使用固定的 Arm GCC 12.3 工具链交叉编译。依赖预装在 [.ci/](../.ci/) 的构建环境 Dockerfile 中，CNB 可缓存这些环境。

配置格式、按钮和发布参数依据 [CNB 手动触发文档](https://docs.cnb.cool/zh/build/web-trigger.md)、[Docker 制品库说明](https://docs.cnb.cool/zh/artifact/docker.html)、[构建节点说明](https://docs.cnb.cool/zh/build/build-node.md) 及 [官方附件插件](https://cnb.cool/cnb/plugins/cnbcool/attachments)。

## ReDroid 镜像

按钮中的 `VENDOR_ARCHIVE_URL` 必须直接返回 `Orangepi6plus_1.0.1_android14_linux6.1.44.7z`。可以使用自己存放官方原文件的公开地址；Google Drive 分享页面、需要浏览器确认或登录的页面不适用。脚本按 `config/inputs.lock.json` 校验 SHA256，不接受其他版本。

表单不是密钥存储，含签名或凭据的 URL 应放入 [CNB 密钥仓库](https://docs.cnb.cool/zh/repo/secret.md)，并在 `.cnb.yml` 的 ReDroid Pipeline 中通过 `imports` 导入 `VENDOR_ARCHIVE_URL`；同时移除按钮中的必填 URL 输入。下载脚本不会主动打印 URL，产物也不记录 URL。

流水线使用 CNB 临时构建凭据，将已构建镜像推送到：

```text
${CNB_DOCKER_REGISTRY}/${CNB_REPO_SLUG_LOWERCASE}/redroid:14
${CNB_DOCKER_REGISTRY}/${CNB_REPO_SLUG_LOWERCASE}/redroid:build-${CNB_BUILD_ID}
```

`14` 表示 Android 14，随每次成功的手动构建更新；`build-<构建ID>` 用于选定某次构建。镜像不再导出为流水线附件。源码提交记录在镜像的 `org.opencontainers.image.revision` 标签中，许可文件位于镜像内 `/vendor/etc/orangepi6p-redroid/`。

在 Debian ARM64 开发板克隆本项目源码，然后拉取镜像。下列地址中的 `<组织>/<仓库>` 替换为实际 CNB 项目路径：

```sh
git clone https://cnb.cool/<组织>/<仓库>.git orangepi6p-redroid
cd orangepi6p-redroid
docker pull docker.cnb.cool/<组织>/<仓库>/redroid:14
python3 scripts/check-host.py
python3 scripts/run.py --image docker.cnb.cool/<组织>/<仓库>/redroid:14
python3 scripts/check-runtime.py
```

开发板需事先安装 Git、Docker、Python 3，并满足 [宿主内核前提](../kernel/README.md)。私有项目拉取镜像前使用 `docker login docker.cnb.cool --username cnb` 登录，密码填写具有制品读取权限的 CNB 令牌。连接和应用数据位置见 [README](../README.md)。

镜像包含厂商组件和 ReDroid 基础层，各自沿用原许可，发布前应核对再分发条件。只发布源码可继续使用 `scripts/export-source.py`，它排除厂商二进制与所有生成目录。详见 [NOTICE](../NOTICE)。

## 内核 deb

内核流水线固定生成 **`6.6.89-cix-redroid`**，包含树内模块、六个厂商外置模块和本板 DTB。它校验 ARM64 架构、完整 vermagic、Mali 依赖顺序及真实 deb 归档内容，并将对应的内核/驱动源码与最终配置一起打包。

在开发板上解开外层 TAR 后执行：

```sh
sha256sum -c SHA256SUMS
sudo apt install ./linux-image-6.6.89-cix-redroid_*_arm64.deb
```

安装成功时会自动注册 EFI GRUB 启动项并设为默认，保留原厂 `/Image` 和原厂菜单；不会自动重启。ESP 选择、支持的 Debian 布局、恢复方式和完整源码说明见 [内核 README](../kernel/README.md)。

CI 的编译与打包检查不代替开发板启动、GPU / VPU 或游戏测试。实际验证结果和未验证范围见 [验证记录](VALIDATION.md)。
