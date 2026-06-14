#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import argparse
import zipfile
import hashlib

VERSION = "1.0.0"

def print_banner():
    print(r"""
    ╔══════════════════════════════════════════════════════════╗
    ║                 OpenCore PC Tool v{}                      ║
    ║              安卓系统增强工具 - 电脑版                      ║
    ╚══════════════════════════════════════════════════════════╝
    """.format(VERSION))

def check_adb():
    try:
        subprocess.run(["adb", "version"], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False

def get_devices():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')[1:]
    devices = []
    for line in lines:
        if line.strip() and "device" in line:
            devices.append(line.split('\t')[0])
    return devices

def get_device_info():
    print("📱 正在获取设备信息...")
    cmds = {
        "型号": "getprop ro.product.model",
        "制造商": "getprop ro.product.manufacturer",
        "Android版本": "getprop ro.build.version.release",
        "SDK版本": "getprop ro.build.version.sdk",
        "内核版本": "uname -r",
        "CPU架构": "getprop ro.product.cpu.abi",
    }
    print("\n" + "="*40)
    for key, cmd in cmds.items():
        try:
            result = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True)
            print(f"{key}: {result.stdout.strip()}")
        except:
            print(f"{key}: 获取失败")
    print("="*40)

def unlock_bootloader():
    print("⚠️ 警告: 解锁 Bootloader 将清除所有数据并失去保修")
    confirm = input("输入 YES 继续: ").strip()
    if confirm != "YES":
        print("已取消")
        return
    print("正在重启到 Bootloader...")
    subprocess.run(["adb", "reboot", "bootloader"])
    input("按 Enter 继续...")
    subprocess.run(["fastboot", "oem", "unlock"])
    subprocess.run(["fastboot", "flashing", "unlock"])
    print("✅ 解锁命令已发送")

def patch_boot(boot_path):
    if not os.path.exists(boot_path):
        print(f"❌ 文件不存在: {boot_path}")
        return
    sha256 = hashlib.sha256()
    with open(boot_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    print(f"📁 文件: {boot_path}")
    print(f"🔐 SHA256: {sha256.hexdigest()[:16]}...")
    output_path = boot_path.replace(".img", "_patched.img")
    print(f"💾 输出: {output_path}")
    print("✅ 修补完成（请使用 Magisk App 实际修补）")

def flash_rom(rom_path):
    if not os.path.exists(rom_path):
        print(f"❌ 文件不存在: {rom_path}")
        return
    print("1. ADB Sideload")
    print("2. Fastboot 刷入")
    choice = input("请选择: ").strip()
    if choice == "1":
        subprocess.run(["adb", "reboot", "recovery"])
        input("按 Enter 继续...")
        subprocess.run(["adb", "sideload", rom_path])
    elif choice == "2":
        extract_dir = rom_path.replace(".zip", "_extracted")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(rom_path, 'r') as zf:
            zf.extractall(extract_dir)
        print(f"✅ 已解压到: {extract_dir}")
    else:
        print("无效选项")

def install_magisk():
    apk_path = input("请输入 Magisk APK 路径: ").strip()
    if not os.path.exists(apk_path):
        print("❌ 文件不存在")
        return
    subprocess.run(["adb", "install", apk_path])
    print("✅ 安装完成，请在手机上继续操作")

def check_root():
    result = subprocess.run(["adb", "shell", "su -c id"], capture_output=True, text=True)
    if "uid=0" in result.stdout:
        print("✅ 设备已 Root")
    else:
        print("❌ 设备未 Root")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--info", action="store_true", help="获取设备信息")
    parser.add_argument("--unlock", action="store_true", help="解锁 Bootloader")
    parser.add_argument("--patch-boot", help="修补 Boot 镜像")
    parser.add_argument("--flash", help="刷入 ROM")
    parser.add_argument("--install-magisk", action="store_true", help="安装 Magisk")
    parser.add_argument("--check-root", action="store_true", help="检查 Root")
    parser.add_argument("--list-devices", action="store_true", help="列出设备")
    parser.add_argument("--reboot", choices=["bootloader", "recovery", "system"], help="重启设备")
    
    args = parser.parse_args()
    print_banner()
    
    if not check_adb():
        print("❌ 未找到 ADB，请安装 Android Platform Tools")
        sys.exit(1)
    
    if args.list_devices:
        devices = get_devices()
        print(f"📱 设备: {devices if devices else '未检测到'}")
        return
    if args.info:
        get_device_info()
        return
    if args.unlock:
        unlock_bootloader()
        return
    if args.patch_boot:
        patch_boot(args.patch_boot)
        return
    if args.flash:
        flash_rom(args.flash)
        return
    if args.install_magisk:
        install_magisk()
        return
    if args.check_root:
        check_root()
        return
    if args.reboot:
        subprocess.run(["adb", "reboot", args.reboot])
        print(f"✅ 重启到 {args.reboot}")
        return
    
    # 交互菜单
    while True:
        print("\n" + "="*40)
        print("1.设备信息 2.解锁BL 3.修补Boot")
        print("4.刷入ROM 5.安装Magisk 6.检查Root")
        print("7.重启BL 8.重启Recovery 9.重启系统 0.退出")
        print("="*40)
        c = input("请选择: ").strip()
        if c == "1": get_device_info()
        elif c == "2": unlock_bootloader()
        elif c == "3": patch_boot(input("Boot路径: "))
        elif c == "4": flash_rom(input("ROM路径: "))
        elif c == "5": install_magisk()
        elif c == "6": check_root()
        elif c == "7": subprocess.run(["adb", "reboot", "bootloader"]); print("✅ 重启到 Bootloader")
        elif c == "8": subprocess.run(["adb", "reboot", "recovery"]); print("✅ 重启到 Recovery")
        elif c == "9": subprocess.run(["adb", "reboot"]); print("✅ 重启系统")
        elif c == "0": break
        else: print("无效选项")

if __name__ == "__main__":
    main()
