#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import zipfile
import urllib.request
import shutil
import time
import struct
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional

# ---------- 黑绿配色 ----------
GREEN = '\033[32m'
BLACK_BG = '\033[40m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_green(text):
    print(f"{BLACK_BG}{GREEN}{text}{RESET}")

def print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_green("""
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║           OpenCore PC Tool  –  黑绿极客完整版                           ║
    ║    一键 ADB/Fastboot · 设备全检测 · 分区备份 · 镜像解包 · 万能刷机      ║
    ╚═══════════════════════════════════════════════════════════════════════════╝
    """)

# ---------- 工具路径 ----------
TOOL_DIR = Path("./opencore_tools")
ADB_EXE = TOOL_DIR / "adb.exe"
FASTBOOT_EXE = TOOL_DIR / "fastboot.exe"
PLATFORM_TOOLS_ZIP = TOOL_DIR / "platform-tools.zip"

# ---------- 下载 ADB/Fastboot ----------
def download_platform_tools():
    if ADB_EXE.exists() and FASTBOOT_EXE.exists():
        print_green("[✓] ADB 和 Fastboot 已存在")
        return True

    print_green("[*] 正在下载 platform-tools ...")
    url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    try:
        urllib.request.urlretrieve(url, PLATFORM_TOOLS_ZIP)
    except Exception as e:
        print_green(f"[✗] 下载失败: {e}")
        return False

    print_green("[*] 解压中 ...")
    with zipfile.ZipFile(PLATFORM_TOOLS_ZIP, 'r') as zip_ref:
        zip_ref.extractall(TOOL_DIR)
    for f in (TOOL_DIR / "platform-tools").glob("*"):
        shutil.move(str(f), str(TOOL_DIR))
    os.rmdir(TOOL_DIR / "platform-tools")
    PLATFORM_TOOLS_ZIP.unlink()
    print_green("[✓] ADB/Fastboot 安装完成")
    return True

def run_cmd(cmd, timeout=60):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", -1
    except Exception as e:
        return "", str(e), -1

# ---------- 设备检测 ----------
def detect_device():
    print_green("\n[检测] ADB 设备 ...")
    out, err, code = run_cmd(f"{ADB_EXE} devices")
    lines = out.splitlines()
    adb_devices = [line.split()[0] for line in lines if line and "device" in line and not "List" in line]
    if adb_devices:
        print_green(f"[✓] 检测到 ADB 设备: {adb_devices[0]}")
        return "adb", adb_devices[0]

    print_green("[检测] Fastboot 设备 ...")
    out, err, code = run_cmd(f"{FASTBOOT_EXE} devices")
    lines = out.splitlines()
    fastboot_devices = [line.split()[0] for line in lines if line and "fastboot" in line]
    if fastboot_devices:
        print_green(f"[✓] 检测到 Fastboot 设备: {fastboot_devices[0]}")
        return "fastboot", fastboot_devices[0]

    print_green("[✗] 未检测到任何设备，请连接手机并开启调试模式。")
    return None, None

# ---------- 获取分区列表 ----------
def get_partitions(mode, device):
    if mode == "adb":
        # 通过 adb shell 获取 by-name 分区
        cmd = f"{ADB_EXE} shell \"ls /dev/block/by-name/\" 2>/dev/null"
        out, err, code = run_cmd(cmd)
        if out:
            return [p.strip() for p in out.splitlines() if p.strip()]
        # 备用：尝试从 /proc/partitions 或 /dev/block/
        cmd = f"{ADB_EXE} shell \"ls /dev/block/platform/*/by-name/\" 2>/dev/null"
        out2, err2, code2 = run_cmd(cmd)
        if out2:
            return [p.strip() for p in out2.splitlines() if p.strip()]
        print_green("[!] 无法获取分区列表，请手动输入分区名。")
        return []
    elif mode == "fastboot":
        # fastboot 模式下可通过 getvar partition-type:xxx 获取，但较慢，这里提示手动
        print_green("[!] Fastboot 模式下无法自动列出分区，请手动输入分区名。")
        return []
    return []

# ---------- 备份分区 ----------
def backup_partitions():
    mode, device = detect_device()
    if not device:
        return

    print_green("\n[备份] 检测分区列表 ...")
    partitions = get_partitions(mode, device)
    if partitions:
        print_green(f"[✓] 找到 {len(partitions)} 个分区:")
        for i, p in enumerate(partitions):
            print_green(f"  {i+1}. {p}")
        print_green("\n请输入要备份的分区编号（逗号分隔，如 1,3,5），或输入 'all' 备份全部重要分区（modem,efs,persist,boot,recovery）")
        choice = input("> ").strip()
        if choice.lower() == 'all':
            important = ["modem", "efs", "persist", "boot", "recovery", "fsg", "modemst1", "modemst2"]
            selected = [p for p in partitions if p in important]
            if not selected:
                print_green("[!] 未匹配到重要分区，将备份全部分区。")
                selected = partitions
        else:
            try:
                indices = [int(x.strip()) for x in choice.split(',') if x.strip().isdigit()]
                selected = [partitions[i-1] for i in indices if 1 <= i <= len(partitions)]
            except:
                print_green("[✗] 输入格式错误")
                return
    else:
        print_green("[!] 无法自动获取分区，请输入要备份的分区名（逗号分隔），例如: modem,efs,boot")
        sel = input("> ").strip()
        selected = [p.strip() for p in sel.split(',') if p.strip()]
        if not selected:
            print_green("[✗] 未选择任何分区")
            return

    backup_dir = Path("./backup_" + time.strftime("%Y%m%d_%H%M%S"))
    backup_dir.mkdir(exist_ok=True)
    print_green(f"[*] 备份目录: {backup_dir}")

    for part in selected:
        print_green(f"[*] 备份分区: {part} ...")
        if mode == "adb":
            # 使用 dd 备份
            cmd = f"{ADB_EXE} shell \"dd if=/dev/block/by-name/{part} of=/sdcard/{part}.img\""
            out, err, code = run_cmd(cmd)
            if code == 0:
                pull_cmd = f"{ADB_EXE} pull /sdcard/{part}.img {backup_dir}/{part}.img"
                run_cmd(pull_cmd)
                run_cmd(f"{ADB_EXE} shell rm /sdcard/{part}.img")
                print_green(f"[✓] 备份成功 -> {backup_dir}/{part}.img")
            else:
                # 尝试直接备份 /dev/block/ 下的设备
                cmd2 = f"{ADB_EXE} shell \"dd if=/dev/block/{part} of=/sdcard/{part}.img\""
                out2, err2, code2 = run_cmd(cmd2)
                if code2 == 0:
                    pull_cmd = f"{ADB_EXE} pull /sdcard/{part}.img {backup_dir}/{part}.img"
                    run_cmd(pull_cmd)
                    run_cmd(f"{ADB_EXE} shell rm /sdcard/{part}.img")
                    print_green(f"[✓] 备份成功 -> {backup_dir}/{part}.img")
                else:
                    print_green(f"[✗] 备份 {part} 失败: {err}")
        else:
            # Fastboot 模式下只能通过 fastboot getvar 或 fastboot flash 读取，这里提示不支持
            print_green(f"[!] Fastboot 模式不支持 dd 备份，请切换到 ADB 模式。跳过 {part}。")

    print_green(f"[✓] 备份完成，文件保存在 {backup_dir}")

# ---------- 解包 boot/recovery ----------
def unpack_image():
    img_path = input("\n请输入要解包的镜像路径 (boot.img / recovery.img): ").strip()
    if not os.path.isfile(img_path):
        print_green("[✗] 文件不存在")
        return

    print_green("[*] 分析镜像 ...")
    out_dir = Path("./unpacked_" + Path(img_path).stem)
    out_dir.mkdir(exist_ok=True)

    with open(img_path, "rb") as f:
        data = f.read()

    # 检查 magic
    magic = data[:8]
    if magic == b'ANDROID!':
        # Android 标准 boot 镜像
        print_green("[✓] 识别为 Android boot 镜像")
        kernel_size = struct.unpack("<I", data[8:12])[0]
        ramdisk_size = struct.unpack("<I", data[16:20])[0]
        page_size = struct.unpack("<I", data[36:40])[0]
        kernel_start = page_size
        kernel_end = kernel_start + kernel_size
        ramdisk_start = (kernel_end + page_size - 1) // page_size * page_size
        ramdisk_end = ramdisk_start + ramdisk_size

        kernel_data = data[kernel_start:kernel_end]
        ramdisk_data = data[ramdisk_start:ramdisk_end]

        (out_dir / "kernel").write_bytes(kernel_data)
        (out_dir / "ramdisk.gz").write_bytes(ramdisk_data)

        # 解压 ramdisk 如果为 gzip
        try:
            import gzip
            with gzip.open(out_dir / "ramdisk.gz", 'rb') as f:
                ramdisk_uncompressed = f.read()
            (out_dir / "ramdisk").write_bytes(ramdisk_uncompressed)
            print_green("[✓] Ramdisk 解压成功")
        except:
            print_green("[!] Ramdisk 非 gzip 格式，保留为原样")

        header = {
            "magic": magic.decode(),
            "kernel_size": kernel_size,
            "ramdisk_size": ramdisk_size,
            "page_size": page_size
        }
        with open(out_dir / "header.json", "w") as f:
            json.dump(header, f, indent=2)

        print_green(f"[✓] 解包完成，输出目录: {out_dir}")

    elif data[:4] == b'\x89\x50\x4e\x47' or data[:2] == b'\x1f\x8b':
        print_green("[✓] 疑似 RAW 或压缩包，直接复制")
        (out_dir / "raw_data").write_bytes(data)
        print_green(f"[✓] 数据已保存到 {out_dir}/raw_data")
    else:
        print_green("[✗] 未知镜像格式，仅保存原始数据")
        (out_dir / "raw_data").write_bytes(data)

# ---------- 刷机 ----------
def flash_device():
    mode, device = detect_device()
    if not device:
        return

    print_green("\n[刷机] 请选择刷入类型:")
    print_green("  1. 刷入单个 img 分区")
    print_green("  2. 从线刷包 (zip) 刷入 (自动解压并刷入所有分区)")
    choice = input("请输入数字: ").strip()

    if choice == "1":
        partition = input("请输入分区名 (如 boot, system, vendor): ").strip()
        img_path = input("请输入镜像路径: ").strip()
        if not os.path.isfile(img_path):
            print_green("[✗] 镜像文件不存在")
            return
        # 如果当前是 adb，先重启到 fastboot
        if mode == "adb":
            print_green("[*] 正在重启到 fastboot 模式 ...")
            run_cmd(f"{ADB_EXE} reboot bootloader")
            time.sleep(5)
            mode, device = detect_device()
            if mode != "fastboot":
                print_green("[✗] 无法进入 fastboot 模式")
                return

        cmd = f"{FASTBOOT_EXE} flash {partition} \"{img_path}\""
        print_green(f"[*] 执行: {cmd}")
        out, err, code = run_cmd(cmd, timeout=300)
        if code == 0:
            print_green("[✓] 刷机成功！")
        else:
            print_green(f"[✗] 刷机失败: {err}")

    elif choice == "2":
        zip_path = input("请输入线刷包 ZIP 路径: ").strip()
        if not os.path.isfile(zip_path):
            print_green("[✗] 文件不存在")
            return
        # 解压到临时目录
        extract_dir = Path("./flash_temp")
        extract_dir.mkdir(exist_ok=True)
        print_green("[*] 解压线刷包 ...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # 查找所有 img 文件
        img_files = list(extract_dir.glob("*.img"))
        if not img_files:
            print_green("[✗] 未找到任何 .img 文件，可能不是标准线刷包")
            return

        # 重启到 fastboot
        if mode == "adb":
            print_green("[*] 重启到 fastboot ...")
            run_cmd(f"{ADB_EXE} reboot bootloader")
            time.sleep(5)
            mode, device = detect_device()
            if mode != "fastboot":
                print_green("[✗] 无法进入 fastboot")
                return

        # 刷入每个镜像
        for img in img_files:
            part_name = img.stem  # 文件名作为分区名
            print_green(f"[*] 刷入 {part_name} ...")
            cmd = f"{FASTBOOT_EXE} flash {part_name} \"{img}\""
            out, err, code = run_cmd(cmd, timeout=120)
            if code == 0:
                print_green(f"[✓] {part_name} 刷入成功")
            else:
                print_green(f"[✗] {part_name} 刷入失败: {err}")

        print_green("[✓] 所有镜像刷入完成")
        shutil.rmtree(extract_dir)
    else:
        print_green("[✗] 无效选项")

# ---------- 主菜单 ----------
def main():
    if not download_platform_tools():
        print_green("[✗] 无法获取 ADB/Fastboot，请检查网络后重试。")
        input("按 Enter 退出...")
        sys.exit(1)

    while True:
        print_banner()
        print_green("  1. 检测设备")
        print_green("  2. 备份分区 (基带/字库/任意分区)")
        print_green("  3. 解包镜像 (boot/recovery)")
        print_green("  4. 刷机 (img 或线刷包)")
        print_green("  5. 退出")
        choice = input("\n请输入选项: ").strip()

        if choice == "1":
            detect_device()
            input("\n按 Enter 继续...")
        elif choice == "2":
            backup_partitions()
            input("\n按 Enter 继续...")
        elif choice == "3":
            unpack_image()
            input("\n按 Enter 继续...")
        elif choice == "4":
            flash_device()
            input("\n按 Enter 继续...")
        elif choice == "5":
            print_green("退出。")
            sys.exit(0)
        else:
            print_green("[✗] 无效选项")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_green("\n[!] 用户中断")
        sys.exit(0)