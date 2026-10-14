#!/usr/bin/env python3
"""Board terminal GPU/VPU monitor; read-only unless --enable-vpu is explicit.
The optional VPU statistics switch is restored on normal exit, Ctrl+C, TERM/HUP.
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
PERF = Path('/sys/kernel/debug/amvx/log/group/perf')
GPU = Path('/sys/kernel/debug/mali0')

def read(path):
    try:
        return Path(path).read_text().replace('\x00', '').strip()
    except OSError as error:
        return f'Unavailable: {error.strerror}'

def number(path):
    value = read(path)
    return int(value) if value.isdigit() else None

def sample():
    raw = read(GPU/'dvfs_utilization')
    values = {k: int(v) for k, v in re.findall(r'(busy_time|idle_time|protm_time):\s*(\d+)', raw)}
    total = values.get('busy_time', 0) + values.get('idle_time', 0)
    busy = values['busy_time'] / total * 100 if total else None
    mem = re.search(r'^mali\d+\s+(\d+)', read(GPU/'gpu_memory'))
    vpu_raw = read(PERF/'utilization')
    match = re.search(r'VPU Utilization:\s*([\d.]+)%', vpu_raw)
    vpu = float(match[1]) if match else None
    fps_raw = read(PERF/'realtime_fps')
    return {
        'time': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'gpu_busy_percent_latest_driver_window': busy,
        'gpu_dvfs_raw': raw,
        'gpu_frequency_hz': number('/sys/class/devfreq/CIXH5000:00/cur_freq'),
        'gpu_allocated_mib': int(mem[1])*os.sysconf('SC_PAGE_SIZE')/(1024**2) if mem else None,
        'vpu_busy_percent_driver_window': vpu,
        'vpu_utilization_raw': vpu_raw,
        'vpu_frequency_hz': number('/sys/class/devfreq/CIXH3010:00/cur_freq'),
        'vpu_stats_enable': read(PERF/'enable'),
        'vpu_realtime_fps_raw': fps_raw,
        'vpu_sampling_note': 'Only sessions created after enabling profiling are covered. FPS needs >200 frames; old sessions can be omitted even when utilization reads 0%.',
    }

def format_number(value, suffix, scale=1):
    return f'{value/scale:.1f}{suffix}' if value is not None else 'N/A'

def display(item, clear):
    if clear:
        print('\033[H\033[2J', end='')
    print('Orange Pi 6 Plus GPU / VPU  ' + item['time'])
    print('GPU 忙碌率: ' + format_number(item['gpu_busy_percent_latest_driver_window'], '%') +
          '   频率: ' + format_number(item['gpu_frequency_hz'], ' MHz', 1e6) +
          '   驱动分配内存: ' + format_number(item['gpu_allocated_mib'], ' MiB'))
    print('VPU 忙碌率: ' + format_number(item['vpu_busy_percent_driver_window'], '%') +
          '   频率: ' + format_number(item['vpu_frequency_hz'], ' MHz', 1e6) +
          '   统计开关: ' + item['vpu_stats_enable'])
    print('VPU 编解码会话实时帧率（驱动原文）:')
    print(item['vpu_realtime_fps_raw'] or '当前未返回会话帧率')
    if item['vpu_busy_percent_driver_window'] is None:
        print('VPU状态: ' + item['vpu_utilization_raw'])
    if item['gpu_busy_percent_latest_driver_window'] is None:
        print('GPU状态: ' + item['gpu_dvfs_raw'])
    print('GPU含宿主及所有容器，为最近DVFS窗口；不是CPU占用或游戏FPS。')
    print('VPU仅覆盖开启统计后新建的会话，需先开监视器再连scrcpy；FPS需超过200帧。')
    print('Ctrl+C退出。VPU统计关闭时显示N/A，不能解释为0%。', flush=True)

def interrupted(signum, frame):
    raise KeyboardInterrupt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval', type=float, default=1, help='刷新间隔，秒，至少0.5')
    parser.add_argument('--samples', type=int, default=0, help='0表示持续显示；正数为有限采样')
    parser.add_argument('--json', action='store_true', help='每行输出JSON，可重定向到项目日志')
    parser.add_argument('--no-clear', action='store_true')
    parser.add_argument('--enable-vpu', action='store_true', help='临时将VPU统计开关设为3，退出恢复原值')
    args = parser.parse_args()
    if args.interval < .5 or args.samples < 0:
        parser.error('interval必须>=0.5，samples必须>=0')
    if os.geteuid() != 0:
        parser.error('debugfs需要root读取，请在板上使用sudo python3运行本脚本')
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    original = None
    recovery = None
    lock = None
    try:
        if args.enable_vpu:
            work = PROJECT/'work/tmp/hw-monitor'
            work.mkdir(parents=True, exist_ok=True)
            lock = (work/'vpu-stats.lock').open('a')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('已有一个启用VPU统计的监视器，请复用或先结束它')
            if list(work.glob('recovery-*.json')):
                raise RuntimeError('存在未完成的统计恢复记录，请先检查，避免覆盖原状态')
            original = number(PERF/'enable')
            if original not in (0, 1, 2, 3):
                raise RuntimeError('无法读取/识别VPU统计原值，未修改开关')
            recovery = work/f'recovery-{os.getpid()}.json'
            recovery.write_text(json.dumps({'path': str(PERF/'enable'), 'original': original,
                                             'pid': os.getpid(), 'boot_id': read('/proc/sys/kernel/random/boot_id')})+'\n')
            (PERF/'enable').write_text('3\n')
            print(f'VPU统计临时开启（原值{original}），退出恢复。', file=sys.stderr, flush=True)
        count = 0
        while True:
            start = time.monotonic()
            item = sample()
            if args.json:
                print(json.dumps(item, ensure_ascii=False), flush=True)
            else:
                display(item, sys.stdout.isatty() and not args.no_clear)
            count += 1
            if args.samples and count >= args.samples:
                break
            time.sleep(max(0, args.interval - (time.monotonic() - start)))
    finally:
        if original is not None and recovery is not None:
            (PERF/'enable').write_text(str(original)+'\n')
            recovery.unlink(missing_ok=True)
            print(f'VPU统计已恢复为{original}。', file=sys.stderr, flush=True)
        if lock is not None:
            lock.close()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
