#!/usr/bin/env python3
"""小红书数据导出 —— 打开浏览器等下载，自动检测"""

import warnings
warnings.filterwarnings("ignore")

import os, sys, time, glob
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.expanduser("~/.xhs_playwright_profile")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")


def main():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    before = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))

    print("🚀 打开小红书创作者中心...")
    print("🔗 https://creator.xiaohongshu.com/")
    print("👉 请自行导航到「数据中心」→「笔记数据」→ 点「导出」")
    print("⏳ 浏览器保持打开，检测到 Excel 文件后自动关闭...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            accept_downloads=True,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()
        page.goto("https://creator.xiaohongshu.com/", timeout=30000)
        page.bring_to_front()

        # 等下载 —— 最长 5 分钟
        for _ in range(300):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                time.sleep(2)  # 等写入完成
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                print(f"✅ {os.path.basename(f)}")
                context.close()
                print(f"EXPORT_FILE:{f}")
                return

        print("⚠️  超时")
        context.close()


if __name__ == "__main__":
    main()
