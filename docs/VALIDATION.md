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
