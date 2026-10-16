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
