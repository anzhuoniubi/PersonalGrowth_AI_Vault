#!/usr/bin/env python3
"""小红书数据自动导出 —— 三步走：登录检测→自动导航→点击导出"""

import warnings
warnings.filterwarnings("ignore")

import os, sys, time, glob, re
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.expanduser("~/.xhs_playwright_profile")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")


def wait_and_click(page, selectors, timeout=5000):
    """依次尝试选择器，点中即返回 True"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            print(f"  ✅ 点击: {sel}")
            return True
        except:
            continue
    return False


def main():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    before = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))

    print("🚀 启动浏览器...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            accept_downloads=True,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        # ── Step 1: 打开创作者中心 ──
        print("📋 打开创作者中心...")
        page.goto("https://creator.xiaohongshu.com/")
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)

        # 检查是否需要登录
        current_url = page.url
        if any(kw in current_url for kw in ["login", "passport", "signin"]):
            print("⚠️  需要登录，请在浏览器中扫码...")
            try:
                page.wait_for_url(
                    lambda u: not any(kw in u for kw in ["login", "passport", "signin"]),
                    timeout=120000
                )
                print("✅ 登录成功")
            except:
                print("❌ 登录超时")
                context.close()
                sys.exit(1)

        # ── Step 2: 导航到数据中心 ──
        print("📊 导航到数据中心...")

        # 尝试点击左侧导航栏的「数据中心」
        nav_hit = wait_and_click(page, [
            "a:has-text('数据中心')",
            "span:has-text('数据中心')",
            "text=数据中心",
            "[class*='sidebar'] >> text=数据",
            "[class*='nav'] >> text=数据",
            "li:has-text('数据')",
        ])

        if nav_hit:
            time.sleep(3)
            page.wait_for_load_state("networkidle", timeout=15000)
        else:
            # 备用：直接拼URL
            print("  ⚠️  未找到导航，尝试直接访问...")
            page.goto("https://creator.xiaohongshu.com/creator/analytics")
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(3)

        # ── Step 3: 点击内容数据 Tab ──
        print("📋 切换到笔记数据...")
        tab_hit = wait_and_click(page, [
            "text=笔记数据",
            "text=内容数据",
            "text=内容概览",
            "[role='tab']:has-text('笔记')",
            "[role='tab']:has-text('内容')",
        ], timeout=3000)

        if tab_hit:
            time.sleep(2)

        # ── Step 4: 点击导出 ──
        print("🔍 查找导出按钮...")
        export_hit = wait_and_click(page, [
            "button:has-text('导出')",
            "text=导出数据",
            "text=下载明细",
            "text=导出",
            "[class*='export']",
            "[class*='download']",
            "button:has-text('下载')",
            "span:has-text('导出')",
        ])

        if export_hit:
            print("  ✅ 已点击导出")
            # 可能需要确认弹窗
            time.sleep(1)
            # 尝试点确认
            try:
                for sel in ["button:has-text('确认')", "button:has-text('确定')", "text=确认导出"]:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        print("  ✅ 已确认导出")
                        break
            except:
                pass
        else:
            print("  ⚠️  未找到导出按钮，请在浏览器中手动点击...")

        # ── Step 5: 等待文件 ──
        print("⏳ 等待下载完成...")
        for i in range(300):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                time.sleep(3)
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                if os.path.getsize(f) > 1000:  # 确认不是空文件
                    print(f"✅ 导出成功: {os.path.basename(f)}")
                    context.close()
                    print(f"EXPORT_FILE:{f}")
                    return

            # 每30秒提醒一下
            if i > 0 and i % 30 == 0:
                print(f"  ...已等待 {i} 秒，请在浏览器中手动操作导出")

        print("⚠️  超时（5分钟）")
        context.close()


if __name__ == "__main__":
    main()
