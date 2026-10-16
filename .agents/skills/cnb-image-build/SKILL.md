---
name: cnb-image-build
description: 排查本项目 CNB ReDroid 镜像构建中的输入、Docker 存储和交叉编译差异。
---

# ReDroid 镜像构建排查

用于本项目镜像构建失败的诊断；修改 CNB 配置时同时使用 cnb-pipeline 技能。

1. 先核对实际构建提交及首个失败步骤，避免将尚未推送的本地修复当成 CI 已使用的代码。
2. 使用用户授权的临时环境时，先检查架构、Docker/Python/编译器版本及已有工作树。将源码快照放入独立目录并核对摘要，保留已有修改；不得为测试重置原工作树。
3. Docker 镜像身份检查见 scripts/common.py。传统存储可能返回 config digest，containerd 存储可能返回 manifest digest，只接受 inputs.lock.json 中固定基线对应的值，同时验证 ARM64、无隐式 volume 和基础文件摘要。不要仅为消除报错就替换固定镜像。
4. Google Gitiles 的归档封装可能变化。若压缩包 SHA 不同，先与此前可信归档逐份比较路径和内容；使用 header-sources.json 的固定文件树摘要及文件数核对，不从未经验证的新包直接生成可信值。规则见 docs/TECHNICAL.md。
5. 按 .cnb.yml 顺序检查资源包导入、基础镜像 prepare、头文件、资源库编译和 image.py。amd64 调试需要额外 ARM64 GNU binutils；记录与正式 ARM64 runner 的差别，不能称为原生 ARM64 CI 已通过。
6. 从未启动的容器读回 payload，对照 work/payload-manifest.json 校验内容与 root 所有权，并核对架构、volume 和基础层。保存原始失败/成功日志、源码摘要和验证报告至项目 work 目录；取回证据后核对 SHA。
7. 将手动构建、正式 CI、registry 上传和开发板运行分别记录。构建测试不包含发布授权，不需要为验证构建启动 Android。推送 CI 修复后遵循 cnb-pipeline 的不轮询要求。

历史验证结果见 docs/VALIDATION.md；不要将旧镜像运行证据替代新构建的硬件验收。
