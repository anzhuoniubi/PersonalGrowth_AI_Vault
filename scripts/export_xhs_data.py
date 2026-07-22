#!/usr/bin/env python3
"""小红书数据自动导出 —— 打开浏览器等下载，自动检测完成"""

import warnings
warnings.filterwarnings("ignore")

import os, sys, time, glob
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.expanduser("~/.xhs_playwright_profile")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")


def main():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    before = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))

    print("🚀 打开创作者中心...")
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
        time.sleep(3)

        # 尝试自动导航到数据中心
        try:
            page.goto("https://creator.xiaohongshu.com/creator/analytics/content",
                     timeout=10000)
            time.sleep(2)
        except:
            pass

        # 尝试自动点击导出
        for sel in ["text=导出数据", "text=下载明细", "button:has-text('导出')"]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    print(f"✅ 已点击导出")
                    break
            except:
                pass

        print("⏳ 等待 Excel 下载（请在浏览器中手动操作导出）...")
        print("   浏览器保持打开，检测到新文件后自动继续...")

        # 等待下载完成 —— 最长等待 3 分钟
        for i in range(180):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                # 等文件大小稳定
                time.sleep(3)
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                print(f"✅ 已检测到: {os.path.basename(f)}")
                context.close()
                print(f"EXPORT_FILE:{f}")
                return

        print("⚠️  超时，请手动下载后重新点击复盘按钮")
        context.close()


if __name__ == "__main__":
    main()
