#!/usr/bin/env python3
"""小红书数据导出 — 打开页面等文件，不猜UI"""

import warnings; warnings.filterwarnings("ignore")
import os, sys, time, glob
from playwright.sync_api import sync_playwright

UD = os.path.expanduser("~/.xhs_playwright_profile")
DL = os.path.expanduser("~/Downloads")

def main():
    for f in ["SingletonLock","SingletonCookie","SingletonSocket","lockfile"]:
        p = os.path.join(UD, f)
        if os.path.exists(p): os.remove(p)
    os.makedirs(UD, exist_ok=True)

    before = set(glob.glob(os.path.join(DL, "笔记列表明细表*.xlsx")))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            UD, headless=False, accept_downloads=True,
            viewport={"width":1280,"height":800}, locale="zh-CN")
        page = ctx.new_page()

        # 直接打开数据中心URL（跳过UI导航）
        print("📋 打开数据中心...")
        try:
            page.goto("https://creator.xiaohongshu.com/creator/analytics/content",
                      timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)
        except:
            page.goto("https://creator.xiaohongshu.com/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)

        time.sleep(3)

        # 登录检测
        if any(k in page.url for k in ["login","passport","signin"]):
            print("⚠️  请扫码登录...")
            try:
                page.wait_for_url(
                    lambda u: not any(k in u for k in ["login","passport","signin"]),
                    timeout=120000)
                print("✅ 登录成功")
                time.sleep(3)
            except:
                print("❌ 登录超时")
                ctx.close(); sys.exit(1)

        # 不再猜UI了，直接等文件
        print("⏳ 请在浏览器中手动操作：")
        print("   数据中心 → 笔记数据 → 导出")
        print("   脚本自动检测下载完成...")

        for i in range(300):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DL, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                time.sleep(3)
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                if os.path.getsize(f) > 500:
                    print(f"✅ 下载完成: {os.path.basename(f)}")
                    ctx.close()
                    print(f"EXPORT_FILE:{f}")
                    return
            if i == 120:
                print("⏳ 已等2分钟，继续监听...")
        print("❌ 超时（5分钟）")
        ctx.close(); sys.exit(1)

if __name__ == "__main__":
    main()
