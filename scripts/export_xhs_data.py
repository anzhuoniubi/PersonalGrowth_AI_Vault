#!/usr/bin/env python3
"""
小红书数据自动导出脚本
用法: python3 export_xhs_data.py

首次运行：手动登录小红书创作者中心，cookie 自动保存
后续运行：自动复用 cookie，一键导出数据
"""

import warnings
warnings.filterwarnings("ignore")

import os, sys, time, glob
from playwright.sync_api import sync_playwright

# 配置
USER_DATA_DIR = os.path.expanduser("~/.xhs_playwright_profile")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
CREATOR_URL = "https://creator.xiaohongshu.com/"

def main():
    print("🚀 启动小红书数据导出...")

    os.makedirs(USER_DATA_DIR, exist_ok=True)

    # 记录导出前的文件列表
    before = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))

    with sync_playwright() as p:
        # 持久化浏览器上下文 —— 登录态自动保存
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,  # 可视化，方便首次登录
            accept_downloads=True,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )

        page = context.new_page()

        # 打开创作者中心
        print("📋 打开创作者中心...")
        page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=30000)

        # 等待页面加载，判断是否需要登录
        time.sleep(2)

        # 检查是否已登录
        if "login" in page.url.lower() or "passport" in page.url.lower():
            print("\n⚠️  首次使用，请手动扫码登录")
            print("   登录完成后脚本会自动继续...")
            # 等待用户登录（最多 120 秒）
            try:
                page.wait_for_url("**/creator/**", timeout=120000)
                print("✅ 登录成功！Cookie 已保存")
            except:
                print("❌ 登录超时，请重试")
                context.close()
                sys.exit(1)

        # 导航到数据中心 - 笔记数据
        print("📊 导航到数据中心...")
        try:
            page.goto("https://creator.xiaohongshu.com/creator/analytics/content",
                     wait_until="domcontentloaded", timeout=15000)
        except:
            # 备用方式：点击导航
            page.click("text=数据中心", timeout=10000)
            time.sleep(2)

        time.sleep(3)

        # 查找并点击数据导出按钮
        print("🔍 查找导出按钮...")

        # 尝试多个可能的导出按钮文本和选择器
        export_selectors = [
            "text=导出数据",
            "text=下载明细",
            "text=导出",
            "button:has-text('导出')",
            "[class*='export']",
            "[class*='download']",
            "text=笔记列表明细",
        ]

        clicked = False
        for selector in export_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=3000):
                    page.locator(selector).first.click()
                    print(f"✅ 点击: {selector}")
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            print("\n⚠️  未能自动找到导出按钮")
            print("   请手动点击导出，脚本等待下载完成...")
            print("   （后续会使用保存的 cookie，这次手动操作一次即可）")

        # 等待新文件下载
        print("⏳ 等待文件下载...")
        download_timeout = 60
        for i in range(download_timeout):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))
            new_files = after - before
            if new_files:
                new_file = sorted(new_files, key=os.path.getmtime, reverse=True)[0]
                print(f"✅ 下载完成: {os.path.basename(new_file)}")
                context.close()
                return new_file

        print("\n⚠️  未检测到新下载的文件")
        print("   如果已手动下载，请直接运行复盘脚本:")
        print("   python3 ~/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/weekly_review.py")
        context.close()
        return None


if __name__ == "__main__":
    result = main()
    if result:
        # 导出成功，返回文件路径供 shell 脚本捕获
        print(f"EXPORT_FILE:{result}")
        sys.exit(0)
    else:
        sys.exit(1)
