#!/vendor/bin/sh
# Isolated redroid-gpu only. This replaces the guest/mesa selector, not host drivers.
setprop ro.hardware.egl mali
setprop ro.hardware.gralloc arm
# Use the matching factory Vulkan HAL wrapper; EGL and Vulkan share libGLES_mali.
setprop ro.hardware.vulkan mali
setprop debug.renderengine.backend gles
setprop debug.hwui.renderer skiagl
log -t gpu-config-mali "Experimental Mali EGL + Arm allocator/mapper; ReDroid virtual HWC retained"
