---
name: cnb-kernel-build
description: 排查本项目 CNB 内核子模块准备、组件源码验证和对应源码打包问题。
---

# CNB 内核构建排查

修改流水线时同时使用 cnb-pipeline 技能。先读用户日志中第一个失败步骤，区分 Prepare、输入验证、编译、打包和上传；不要因后续步骤失败就回退已经通过的子模块准备方案。

- 源码位于 kernel/vendor-snapshot/linux 和 components，gitlink 与 kernel/sources.lock.json 固定提交必须一致。内核任务启用 submodules 且 remote=false，镜像任务禁用。构建阶段不自行 fetch。
- 旧缓存可能保留 kernel/upstream/linux 和 components 的独立子模块。合并快照使用独立的 kernel/vendor-snapshot 路径，避免旧嵌套 gitdir 被误判为快照仓库；不要移动回旧父路径，也不要删除用户的旧源码和构建补丁。快照只包含四棵选定公开驱动源码。
- 输入内容修改检查与打包范围都使用 LOCK.components.paths 的四个公开驱动目录。fetch-sources.py 拒绝这些目录相对 HEAD 的暂存/未暂存修改；不得恢复全组件仓库的无路径 diff，也不得关闭实际驱动校验。
- Linux 仍只允许 vendor-o-build.patch 对应的修改。源码包排除 .git 元数据及未选组件目录，项目源码导出排除 kernel/vendor-snapshot、旧 kernel/upstream 和 kernel/work。
- 回归验证使用 python3 kernel/tests/test_kernel.py，覆盖无关二进制变化不阻塞、选定驱动变化仍拒绝。区分这些测试、正式 CI 完整编译与开发板运行；证据见 docs/VALIDATION.md。
