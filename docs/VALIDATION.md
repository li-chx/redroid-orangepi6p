# 验证记录

2026-10-15，本地整理阶段。这里区分历史实验与本次独立发布目录验证，不把构建成功当作所有游戏兼容。

- 独立目录源码重新编译的ComposerResources SHA256：`6ec472bb7384c207002b3eee3d87a6fe66fc5dfa3a70c8b227a3d8a02b5395a7`，与原已使用版本完全一致。
- `prepare.py`已从固定基础镜像的临时**停止容器**读取7份链接/manifest输入并逐份校验SHA，完成后删除该容器；厂商文件按`inputs.lock.json`逐份核对。
- 板上本地派生镜像初次ID：`sha256:0054f9561dab8f6a211bd18eeab2725eedfd4696ad74d6be14e03f64bc31b6c5`。无自动push。
- 空数据实例`redroid-release-test`，ADB仅回环5556，boot_completed1、Mali EGL/Vulkan选择、ARM Mali GLES、CIX Codec2服务running、实际1920×1080/120Hz；只有项目内`/data` bind，无匿名volume。
- 早期读取遇到boot_completed与后台刷新策略写入的竞争窗口，已在检查脚本中增加等待。未因此重复重启容器。
- 原游戏容器及原端口没有被停止或覆盖。本次空数据功能验收不包含游戏APK/账号登录或性能基准。

- 最终受控目录构建上下文约60.18MB，缓存命中并得到相同镜像ID；输入归档方式曾被legacy构建器误当Dockerfile，最终不使用该路径。仅Dockerfile/生成rootfs进入构建上下文。
- 空数据实例强制`c2.cix.avc.encoder`录制1080p/8Mbps/8秒，厂商服务真实持有`/dev/video1`，输出229帧H264，ffprobe与完整CPU解码无错误。设置画面已在本地人工核对正常，Vulkan枚举包含Mali。
- 这段短录带HOME/设置导航动画，只作功能验收，不当作持续游戏FPS、低延迟或性能上限测试。没有向新实例安装游戏。
- 最终镜像约1.65GB（含完整ReDroid/Android基础层，非65KB镜像）；镜像ID不变。测试容器已停止，原游戏容器boot_completed1/GDMactive保持。
- 从官方7z通过本发布目录提取器重新提取，48个必需输入SHA全部匹配。普通用户debugfs不能恢复原始owner的提示不影响内容，Docker COPY明确设置root所有权。没有挂载/刷写系统镜像。
- 内核Makefile补丁对已有已应用源码`git apply --reverse --check`通过；本轮未重编/安装宿主内核。全部Python语法检查通过。
- 源码包采用显式白名单并逐文件SHA，不含厂商库/Android镜像/私钥/游戏/账号数据。未推送Docker registry或创建公开仓库。

旧完整环境已经通过真实游戏/Vulkan与scrcpy H264硬编码，但不将旧容器中的游戏运行冒充新空数据镜像的游戏验收。

本次生成的整张镜像/重复vendor提取暂存已清理；原始官方输入、必要构建payload/cache、研究日志与用户数据保留。

## 2026-10-16：历史 GitHub Actions 入口检查（已由 CNB 替代）

- 添加手动触发的 ReDroid ARM64 镜像构建与 Artifact 下载工作流；当前发布仓库缺少完整内核构建入口，按用户要求不提供内核 CI。目标开发板系统为 Debian。
- 工作流 YAML、各步骤 Bash 语法、Python 语法和本地文档链接检查通过。
- 使用模拟下载响应和替代 Docker 导出进程，验证了错误 SHA256、非 HTTPS 地址、已有下载暂存、Docker 导出失败、镜像 ID 不匹配的处理，以及成功产物的 gzip 内容、文件清单与 SHA256。
- 源码导出包含新增 workflow、辅助脚本和 CI 文档，包内文件 SHA256 校验通过。
- 尚未在 GitHub Actions 上执行完整构建，未生成本轮真实镜像 Artifact，也未重新验收开发板运行；这些检查不替代实际镜像构建和 GPU / VPU 测试。

## 2026-10-16：CNB 流水线与新内核 deb

- 原 GitHub 工作流改为 CNB 的两个手动构建入口：ReDroid 镜像、内核 deb。`.cnb.yml` 的 YAML/语义/Schema 校验和 `.cnb/web_trigger.yml` 的 YAML/目录/Schema 校验均通过；附件插件参数、手动事件及 ARM64 支持已按官方文档与插件实现核对。
- 固定公开 Linux 和厂商组件提交、Arm GCC 12.3.Rel1 与原板完整配置。公开 GPU 的 474 份、NPU 的 45 份 C/头文件/构建文件与原实验源码逐项一致。配置差分主要为 Binder、策略路由和 `-cix-redroid` 后缀；工具识别和新可见选项另有默认值变化。
- 在本地 x86_64 环境完成真实交叉编译和打包：Image、945 个树内模块、6 个厂商模块、DTB，release 均为 `6.6.89-cix-redroid`。完整 vermagic 一致，`depmod` 无诊断，Mali 辅助模块先于主模块的依赖计划通过。
- 实际 deb 的逐文件内容与暂存树 SHA 核对通过，包名 `linux-image-6.6.89-cix-redroid`、架构 ARM64；同时生成对应的已打补丁 Linux/公开驱动源码归档、项目源码包、最终配置及校验清单。
- 12 项隔离测试通过，覆盖启动配置重复执行、根分区不匹配和未知模板拒绝、发布失败恢复、EFI 分区选择、卸载保护、模块架构/vermagic 检查、真实 deb 内容与维护脚本，以及源码归档的 Git/所有者信息排除。生成菜单通过真实 `grub-script-check` 检查。
- 本轮没有在开发板安装 deb、挂载 ESP、发布 GRUB 配置或重启。启动注册仅经过隔离测试，未宣称新 release 已实机启动；CNB 线上完整任务和附件上传也尚未执行。ReDroid 运行证据仍沿用前面的历史验收。

## 2026-10-16：项目 Docker 制品库与 Android 版本标签

- ReDroid 流水线改为推送项目 Docker 制品库，常用标签为 `14`（Android 14），同时保留 `build-<构建ID>`；内核 deb 继续作为提交附件提供。本地构建、运行和离线导出脚本统一使用 `orangepi6p-redroid:14`。
- `.cnb.yml` 与 Web 按钮通过技能指定的 YAML/语义或目录/Schema 校验；Python 语法和发布脚本 Shell 语法通过。
- 使用替代 Docker 命令验证两种标签的目标路径、构建标签上传失败即停止、成功/失败均清理临时认证目录，以及令牌通过标准输入传递。未连接真实制品库。
- 隔离镜像构建检查确认项目及组件许可文件进入 payload 和清单、源码提交号传入 OCI 标签、构建上下文清理；这些检查使用替代构建命令，没有重新构建或启动真实 Android 镜像，也未改动已有内核构建产物。
- 既有实机镜像及历史验证记录中的 `14-gpu-vpu` 保持原样；新标签尚未在线发布。

## 2026-10-16：Debian 构建环境的工具链解压修复

- 用户反馈重跑时两份固定源码均已拉取，随后因 `TarFile.extractall()` 不接受 `filter` 参数失败。本地此前使用较新 Python，未覆盖该构建环境差异。
- 工具链保持固定 URL/SHA256，校验通过后改用 GNU tar / xz 在临时目录解压，保留执行权限和内部链接、不采用归档所有者，完整解压后才发布缓存目录；环境 Dockerfile 显式列出 tar。
- 最终 15 项隔离测试通过，新增检查覆盖不调用 Python 的解压 API、执行权限/符号链接恢复、已完成缓存复用、错误 SHA 拒绝、解压失败清理。CNB 两份配置的指定校验和 Git 空白检查通过。
- 撤下此前针对瞬时 Git 拉取失败准备的未提交配置隔离试改；该网络错误原因尚未确定。本轮未重编完整内核，也未在线重跑修复后的任务，未在开发板安装或启动新内核。

## 2026-10-16：CNB 云端完整构建与 Git 下载调整

- 用户提供的错误发生在 partial clone 的 checkout 补取对象阶段。使用相同 `.ci/kernel.Dockerfile` 在授权的 CNB 云环境建立 Debian 容器，实际版本为 Python 3.11.2、Git 2.39.5，资源为 8 核 / 16GB。原始过滤 fetch 和 checkout 本轮完整成功，认证错误没有稳定复现，具体网络原因仍未确定。
- Linux 改为 shallow fetch 固定提交的完整文件；新检出没有缺失对象，也已包含此前补取失败的对象。厂商组件继续稀疏检出。fetch、checkout 和可能联网的 sparse-checkout 最多尝试三次；支持补齐旧 Linux partial clone 缓存，并在重复执行时保留已应用的构建补丁。
- 18 项测试在本地及该 Debian 容器均通过，覆盖下载重试终止、完整/稀疏检出、旧缓存补齐、补丁保留及此前的解压/启动注册/真实 deb 检查；两份 CNB 配置校验通过。
- 云端完整执行 `kernel/build.sh` 并退出 0：生成 `6.6.89-cix-redroid` Image、945 个树内模块、6 个厂商模块、DTB、ARM64 deb 与对应源码归档。模块验证、Mali 依赖计划、真实 deb 逐文件验证通过，`depmod` 无诊断，最终 SHA256 清单全部通过。
- 此次为基础提交 `5b49844` 加本轮未提交下载修复的手动云端验证，未执行制品上传、内核安装或板端启动。通过完整构建不代表消除了所有间歇性网络错误；未将这次结果冒充正式 CNB 流水线或开发板验收。

## 2026-10-16：Release 厂商资源包接入镜像 CI

- 实际匿名下载用户提供的 CNB Release `tar.gz` 和 `.sha256`，经 HTTPS 重定向后均返回 HTTP 200；资源包 23,754,986 字节，SHA256 为 `a1443419770f84f74985bac3ebbc20d345c9f4076ed6f25b29b2f7f9da408bd1`，与打包版本及 107 字节的校验文件一致。
- 镜像 CI 保留必填 URL 输入 `VENDOR_ARCHIVE_URL`，改为下载锁定的资源包并白名单导入。整体 SHA 固定在独立的 `vendor-bundle.lock.json`，包内清单与原始 48 份文件继续校验；拒绝越界路径、链接、重复/缺失文件，不采用 Python 的版本相关解压过滤 API。
- 7 项隔离测试通过，覆盖导入/缓存复用、损坏缓存和归档、路径/链接/重复/多余项、缺文件/错误内容/不同目录清单、下载摘要与大小限制、非 HTTPS/URL 凭据拒绝。流水线在下载前执行这些检查。
- 使用更新后的真实下载脚本访问上述 Release 成功；在隔离工作目录导入实际资源包，再用已验证的基础镜像文件运行真实 `prepare.py` 成功，48 个原始输入和 7 份基础文件校验通过，生成 55 个待构建文件。已有构建 payload 保持原样。
- CNB 两份配置的指定 YAML/语义或目录/Schema 校验，以及 Python/Shell 语法、文档链接和 Git 空白检查通过。本轮未重新编译或启动 Android 镜像，未触发正式 CI 或发布镜像；运行验收仍沿用历史记录。

## 2026-10-16：CNB SSH 环境完整镜像构建

- 使用用户授权的临时云环境，在独立目录检验基础提交 `d195ac2` 的 65 份源码后加入本轮修复。环境为 amd64、8 核 / 16GB、Docker 29.6.2 containerd 存储；构建容器基于 `.ci/redroid.Dockerfile`，仅额外安装 ARM64 binutils 供交叉链接，Python 3.12.3、Clang 18.1.3、GNU linker 2.42。正式流水线仍使用 ARM64 节点。
- 首次拉取固定基础镜像后发现 Docker 29 返回 manifest digest，而原脚本只接受旧 config digest；修复为兼容这两个锁定值，保留 ARM64 / 无隐式 volume 限制。实际 `prepare.py` 已校验七份基础文件并完成导入。
- 上游 libcxx 归档由 564,851 字节变成 564,822 字节，整包及展开 tar 的 SHA 均不同，但 182 份普通文件的路径与内容逐份一致。头文件校验改为固定文件树摘要及文件数，固定值来自此前已验证的本地归档；不以新下载包的整包摘要替换可信基线。五份归档和独立 ABI 头均通过实际下载校验。
- 最终连续执行 12 项测试、真实 Release 下载、48 份厂商文件导入、基础镜像 prepare、头文件下载、ARM64 资源库编译和 Docker 镜像构建，退出码 0。新增测试覆盖两种镜像 ID、错误架构/隐式 volume 拒绝、头文件重新打包、内容/路径/重复项变化，以及失败下载的缓存处理。
- 生成 `orangepi6p-redroid:14`，ARM64 镜像 ID 为 `sha256:8305671ada8dd365afdf7d3ee9e8f92d09583dce790ca55a2cebf86ab0f810da`；资源库 SHA256 为 `9fa4ab05f28efdb36293674097cf2f6f0fd01575983aae7c5f0a3f73030233f8`。从未启动的验证容器读回全部 60 份 payload，逐文件 SHA 与清单一致、owner 均为 root，基础层保留且无隐式 volume。
- 本地证据位于 `work/image-ci-validation/`，包含完整及失败日志、镜像/导入结果、payload 清单和 `logs/image-validation.json`；取回的 11 份证据均与云端 SHA 一致。验证报告记录基础提交与六份未提交修复文件的摘要，不能将该镜像视为纯 `d195ac2` 的构建结果。
- 本次为手动云端交叉构建，未执行正式 ARM64 CI、registry 上传、Android 启动或开发板 GPU / VPU 验收。已有运行验收仍沿用历史记录。

## 2026-10-16：内核源码改为平台准备的子模块

- Linux 与 components 注册为 `kernel/upstream/` 下的两个 gitlink，仍分别锁定 `f41a4f0b22c0f85a645aa207435761a0123feeaf` 与 `ba3bac4167cd5f115f3eaf4717356d2b3cb923d5`。核对 `.gitmodules`、gitlink 和 `sources.lock.json` 一致，本地已初始化且使用 `.git` 指针文件。CNB 内核任务启用子模块并保持 `remote: false`；ReDroid 镜像任务关闭子模块。
- 移除构建脚本内的源码 fetch / checkout / 重试，保留编译器下载及固定 SHA 检查。使用现有本地对象准备源码，在 `GIT_ALLOW_PROTOCOL=file` 限制下实际运行输入验证成功；四个选定公开驱动目录的 681 份文件与此前已验证输入逐份一致。旧构建目录和源码缓存未删除。
- 20 项内核测试通过，包括真实 Git 新克隆 workspace 的两个子模块初始化、目录及指针形式的 Git 元数据、缺失子模块/错误提交/缺失驱动目录拒绝、重复验证保留补丁、以及已有启动注册和 deb 检查。对应源码包测试额外放入未选公开目录及模拟私有目录，确认两者与 `.git` 元数据均不会进入归档；项目源码导出测试确认 populated submodule 与 work 目录在读取前就被排除。
- 在实际新 Linux 路径临时应用 Makefile 补丁，使用隔离 `O=` 目录完成配置合并、`olddefconfig` 和 `kernelrelease` 检查，结果为 `6.6.89-cix-redroid`；结束后撤销本次测试补丁，子模块保持干净。没有重编完整内核或六个驱动。
- 日志与报告位于 `kernel/work/logs/submodule-tests.log`、`submodule-inputs.log`、`submodule-config.log` 和 `submodule-validation.json`。CNB 两份配置通过指定校验；项目源码包保留 `.gitmodules`，不包含上游源码工作树或 Git 元数据。
- 本轮未提交、推送或触发正式 CNB 构建，未实测新方案在平台上的缓存命中率或 GitHub 冷缓存下载成功率。子模块缓存机制依据官方文档和开源 YYDS 实现，仍需新提交的实际 Prepare 阶段验证。

## 2026-10-16：组件完整检出的修改检查范围

- 用户提供的 19:49:54 CI 日志已通过两份子模块校验与编译器准备，随后在全组件仓库 `git diff --exit-code HEAD` 处失败，列出五份未参与构建的二进制。它们全部位于上游 `.gitattributes` 的 LFS 路径中；日志没有提供 Prepare 与构建容器的完整过滤器配置，因此不将具体的 LFS 处理差异写成已确认原因。
- 移除遗留的全组件仓库修改检查，在 `fetch-sources.py` 中按锁定清单对四个实际构建、打包的公开驱动目录检查相对 HEAD 的差异，并禁用外部 diff 与 textconv。固定提交检查保留，选定源码的暂存/未暂存修改仍拒绝，不覆盖或清理无关二进制。
- 22 项内核测试通过。新增真实 Git 回归检查复现“未使用二进制变化使旧全仓检查退出 1”，而修复后的输入检查通过且保留该文件；另验证实际驱动的暂存、未暂存修改都被拒绝。实际固定子模块与缓存编译器输入检查通过，日志位于 `kernel/work/logs/component-scope-tests.log` 和 `component-scope-inputs.log`。
- 本轮没有修改流水线配置、重新编译完整内核或在线重跑 CI；这些检查不代表后续编译、制品上传或板端启动已通过。


## 2026-10-17 CNB vendor 单仓库快照

- vendor 仓库已更名为 `li_chx/Orangepi6plus-redroid-vendor`；原 Release `1.0` 的两个附件 ID 和 SHA256 保持不变，新地址的 SHA256 附件也已实际下载核对。
- 快照提交为 `46c0c4c46fc2461f2bb4c537b0beb851fe782ba7`，包含完整 Linux tree 与四棵选定的 GPU/NPU/VPU/ISP tree，共 86,010 个文件。Linux tree 为 `cd1e9fb433ab67c27dea245f77162ab46f7744d4`；组件 tree ID 见 `kernel/sources.lock.json` 与 vendor 的 `snapshot.json`。这些 Git tree 与原先固定的上游提交逐项一致，不含本地构建补丁或嵌套 gitlink。
- 主仓库只注册 `kernel/upstream` 一个 CNB submodule，gitlink 与锁定清单指向上述快照。上游 GitHub URL 和提交继续作为来源信息记录，源码初始化不会向 GitHub 克隆；Arm 编译器仍单独下载并校验。
- 使用独立的新工作树，从 CNB 实际执行 `git submodule update --init --recursive`，成功检出固定快照，递归子模块数为 1。随后核对来源清单和五棵 Git tree，实际执行内核补丁首次及重复应用，再反向移除该补丁并确认源码干净。本次初始化及这些检查合计约 14.18 秒，仅是该环境的一次测量。
- 在云端执行 24 项内核测试：23 项通过，1 项因环境缺少 `grub-script-check` 而跳过。覆盖一个快照的新克隆初始化、来源/tree/清单校验、选定驱动修改拒绝、内核补丁幂等性及拒绝其他修改时保留已有内容、源码打包和现有启动/deb 检查。
- Shell 语法检查、项目源码导出通过。对应源码包现在附带 `vendor-snapshot.json`，构建信息同时记录 CNB 快照提交和两个原始上游提交；项目源码导出继续排除 populated submodule 与工作缓存。
- 本次验证针对源码分发、校验、补丁和打包流程，没有重新编译完整内核，也没有进行开发板启动或硬件验收。


## CNB 旧代码缓存迁移修复（2026-10-17）

- 构建 `cnb-mut-1k53uk2vu` 在 Prepare 阶段失败。旧缓存仍有 `kernel/upstream/linux` 和 `components` 的工作树及嵌套 Git 元数据；将快照直接放在 `kernel/upstream` 会使 Git 将旧元数据父目录误判为快照仓库，报 `not a git repository`，编译尚未开始。
- 快照改用独立的 `kernel/vendor-snapshot` 路径和 submodule 名称，固定提交仍为 `46c0c4c46fc2461f2bb4c537b0beb851fe782ba7`。同步更新构建、锁定清单、文档和项目导出；导出同时排除新旧源码目录，不主动清理旧源码工作树。
- 新增真实 Git 迁移回归：初始化两个旧嵌套子模块，复现父路径快照初始化失败，再检出修复版本，执行递归同步与初始化、验证来源及源码 tree，并确认旧目录中的本地文件仍保留。
- Termux 使用标准 `umask 022` 执行 25 项内核测试，24 项通过，1 项因缺少 `grub-script-check` 跳过。Shell 语法、Python 编译、项目源码导出和差异空白检查通过。完整内核编译仍需新的 CNB 构建验证。


## 已发布内核的 CI 构建（2026-10-17）

- 提交 `52c099f5d467b35a018ffb8d24acbfc6e0223895` 的内核流水线 [cnb-u9c-1k53v2noi](https://cnb.cool/li_chx/redroid-orangepi6p/-/build/logs/cnb-u9c-1k53v2noi) 成功完成准备、测试、完整内核与六个厂商模块编译、打包和上传。
- 原始提交附件 `kernel-cnb-u9c-1k53v2noi.tar` 为 224,409,600 字节，SHA256 为 `4b3f721c9287a245116f20c992ec52337a190f7dcab5d194c0741151aeda5148`；下载后核对外层和包内全部 10 项校验值。`build-info.json` 中的源提交、构建 ID 和 vendor 快照提交与构建一致，记录模块总数 951。
- Release 标签 `kernel-6.6.89-cix-redroid-20261017` 指向上述构建提交，保留原始附件和外层 SHA256 文件。CI 成功不等于开发板启动或 GPU/VPU 实机验收。


## 配套镜像的 CI 发布（2026-10-17）

- 同一提交 `52c099f` 的镜像流水线 [cnb-9rb-1k53vpcv5](https://cnb.cool/li_chx/redroid-orangepi6p/-/build/logs/cnb-9rb-1k53vpcv5) 成功，Docker 制品库确认 `14` 与 `build-cnb-9rb-1k53vpcv5` 均为 ARM64 镜像，digest 为 `sha256:988411f51474ab25b2c5953dad7be5dd35ffb6f42ced3724d155be620c1f9308`。
- 地址为 `docker.cnb.cool/li_chx/redroid-orangepi6p/redroid`。流水线与制品标签关联到上述源码提交；这次没有运行新的开发板 Android / GPU / VPU 实测。
