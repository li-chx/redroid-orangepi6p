// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <stddef.h>
#include <stdalign.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include "IMapper.h"

extern "C" void* android_load_sphal_library(const char*, int);

// Per-process diagnostics. One writer holds gMapperLock; readers use sequence.
struct Mapper5Stats {
    uint64_t magic, version, pid, sequence;
    uint64_t imports, frees, importErrors, freeErrors, live, peak;
};
static_assert(sizeof(Mapper5Stats) == 80);
static std::mutex gMapperLock;
static AIMapper* gMapper;
static Mapper5Stats* gStats;

static void initStats() {
    if (gStats) return;
    char name[128];
    snprintf(name, sizeof(name), "/data/gpu-mapper5-stats/resources-%d.stats", getpid());
    int fd = open(name, O_RDWR | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (fd < 0 || ftruncate(fd, sizeof(Mapper5Stats)) != 0) {
        if (fd >= 0) close(fd);
        __android_log_print(ANDROID_LOG_ERROR, "ComposerMapper5", "stats open failed: %s", name);
        return;
    }
    void* memory = mmap(nullptr, sizeof(Mapper5Stats), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (memory == MAP_FAILED) return;
    gStats = static_cast<Mapper5Stats*>(memory);
    memset(gStats, 0, sizeof(*gStats));
    gStats->magic = 0x354d415050455253ULL;
    gStats->version = 1;
    gStats->pid = getpid();
}

static void recordMapper(bool importing, bool success) {
    if (!gStats) return;
    __atomic_add_fetch(&gStats->sequence, 1, __ATOMIC_SEQ_CST);
    if (importing) {
        if (success) {
            ++gStats->imports; ++gStats->live;
            if (gStats->live > gStats->peak) gStats->peak = gStats->live;
        } else ++gStats->importErrors;
    } else {
        if (success) { ++gStats->frees; --gStats->live; }
        else ++gStats->freeErrors;
    }
    __atomic_add_fetch(&gStats->sequence, 1, __ATOMIC_SEQ_CST);
}
