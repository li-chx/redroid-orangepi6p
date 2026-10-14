# 宿主内核前提

本包是容器用户态适配，不会安装内核。已验证宿主是Orange Pi 6 Plus官方6.6路线的派生内核`6.6.89-cix-redroid2`，不是任意ARM64 Linux。

必要的Android/网络增量见`redroid.config`。它需要合入厂商完整配置，不能拿这个小片段替代原板的GPU/NPU/VPU/ISP、存储、ACPI、网络、调频、温控等配置。

源码基线：

- [Orange Pi Linux](https://github.com/orangepi-xunlong/linux-orangepi)，分支`orange-pi-6.6-cix`，本次源码提交`f41a4f0b22c0f85a645aa207435761a0123feeaf`。
- 当前厂商包版本1.0.2；GPU内核mali_kbase r53p0/UK1.36。VPU是amvx，不是Rockchip MPP。
- [component_cix-next](https://github.com/orangepi-xunlong/component_cix-next) 的VPU/ISP参考提交`ba3bac4167cd5f115f3eaf4717356d2b3cb923d5`，当时与板上changelog/16份VPU固件SHA一致；源码与板上包的逐位原始对应关系未证实，不用它覆盖已有固件。

`vendor-o-build.patch`是该内核树的9个Realtek Makefile、23处源码路径修正，用于支持`O=`输出目录。它不修改GPU/VPU功能。应用前用`git apply --check`核对相同基线；本次只从已使用的源码差异导出，未重新编整套内核。

重编时应：以板上 `/proc/config.gz` 为硬件基线 → 应用路径补丁 → 合并本片段/olddefconfig并检查差异 → 用独立release后缀构建Image/modules/DTB → 对同一release重建厂商外置模块。原实验包含Mali平台/内存组/GPU三模块、NPU aipu、VPU amvx、ISP armcb，共六份外置模块，不能只换Image或只得到Binder就认为硬件配套齐全。

本板曾因新增Panthor匹配接管GPU导致厂商桌面黑屏。已验证的测试启动项使用`module_blacklist=panthor`保留Mali内核驱动；运行前应实际检查mali绑定与 `/dev/mali0`，不要只凭黑名单文件存在推断生效。本包不会修改你的启动参数。

Binder可通过内建或正确配套模块提供；不要求每个人都完整重编，但任何替代方案都需要独立验证厂商硬件兼容。网络还必须支持IPv4和IPv6策略路由，否则Android netd会失败。

安装内核/模块/启动项前，核对目标存储和板型、备份原厂可启动入口，明确恢复方法。本最小运行包故意不提供对未知设备自动写盘或改GRUB的脚本。当前已具备上述内核的使用者可以直接构建容器镜像，不必重编内核。
