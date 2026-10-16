---
name: cnb-kernel-build
description: 排查本项目 CNB 内核子模块准备、组件源码验证和对应源码打包问题。
---

# CNB 内核构建排查

修改流水线时同时使用 cnb-pipeline 技能。先读用户日志中第一个失败步骤，区分 Prepare、输入验证、编译、打包和上传；不要因后续步骤失败就回退已经通过的子模块准备方案。

- 源码位于 kernel/upstream/linux 和 components，gitlink 与 kernel/sources.lock.json 固定提交必须一致。内核任务启用 submodules 且 remote=false，镜像任务禁用。构建阶段不自行 fetch。
- 完整 components 子模块包含未使用的 LFS deb/闭源二进制。它们在 Prepare 和构建环境的过滤器处理不同可能显示 diff；不能仅据此断言二进制被损坏或源码版本错误，也不要盲目 reset。
- 输入内容修改检查与打包范围都使用 LOCK.components.paths 的四个公开驱动目录。fetch-sources.py 拒绝这些目录相对 HEAD 的暂存/未暂存修改；不得恢复全组件仓库的无路径 diff，也不得关闭实际驱动校验。
- Linux 仍只允许 vendor-o-build.patch 对应的修改。源码包排除 .git 元数据及未选组件目录，项目源码导出排除 kernel/upstream 和 kernel/work。
- 回归验证使用 python3 kernel/tests/test_kernel.py，覆盖无关二进制变化不阻塞、选定驱动变化仍拒绝。区分这些测试、正式 CI 完整编译与开发板运行；证据见 docs/VALIDATION.md。
