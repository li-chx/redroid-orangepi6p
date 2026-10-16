// SPDX-License-Identifier: MIT
bool ComposerHandleImporter::init() {
    std::lock_guard<std::mutex> lock(gMapperLock);
    if (gMapper) return true;
    void* library = android_load_sphal_library("/vendor/lib64/hw/mapper.arm.so", RTLD_NOW);
    if (!library) {
        __android_log_print(ANDROID_LOG_ERROR, "ComposerMapper5", "mapper load: %s", dlerror());
        return false;
    }
    auto load = reinterpret_cast<AIMapper_Error (*)(AIMapper**)>(dlsym(library, "AIMapper_loadIMapper"));
    AIMapper* mapper = nullptr;
    if (!load || load(&mapper) != AIMAPPER_ERROR_NONE || !mapper ||
        mapper->version < AIMAPPER_VERSION_5 || !mapper->v5.importBuffer || !mapper->v5.freeBuffer)
        return false;
    gMapper = mapper;
    initStats();
    __android_log_print(ANDROID_LOG_INFO, "ComposerMapper5", "source resources initialized mapper=%u pid=%d", mapper->version, getpid());
    return true;
}

Error ComposerHandleImporter::importBuffer(const native_handle_t* rawHandle,
                                          const native_handle_t** outBufferHandle) {
    *outBufferHandle = nullptr;
    if (!rawHandle || (!rawHandle->numFds && !rawHandle->numInts)) return Error::NONE;
    std::lock_guard<std::mutex> lock(gMapperLock);
    if (!gMapper) return Error::NO_RESOURCES;
    AIMapper_Error error = gMapper->v5.importBuffer(rawHandle, outBufferHandle);
    recordMapper(true, error == AIMAPPER_ERROR_NONE);
    if (error != AIMAPPER_ERROR_NONE) {
        __android_log_print(ANDROID_LOG_ERROR, "ComposerMapper5", "import error=%d", error);
        return Error::NO_RESOURCES;
    }
    return Error::NONE;
}

void ComposerHandleImporter::freeBuffer(const native_handle_t* bufferHandle) {
    if (!bufferHandle) return;
    std::lock_guard<std::mutex> lock(gMapperLock);
    if (!gMapper) return;
    AIMapper_Error error = gMapper->v5.freeBuffer(bufferHandle);
    recordMapper(false, error == AIMAPPER_ERROR_NONE);
    if (error != AIMAPPER_ERROR_NONE)
        __android_log_print(ANDROID_LOG_ERROR, "ComposerMapper5", "free error=%d", error);
}
