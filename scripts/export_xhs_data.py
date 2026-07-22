#!/usr/bin/env python3
"""小红书数据自动导出——每步有输出，出错不沉默"""

import warnings
warnings.filterwarnings("ignore")

import os, sys, time, glob
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.expanduser("~/.xhs_playwright_profile")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")


def main():
    # 清理锁文件
    for f in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
        p = os.path.join(USER_DATA_DIR, f)
        if os.path.exists(p):
            os.remove(p)
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    before = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))
    print(f"[初始化] 已有 {len(before)} 个数据文件")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            accept_downloads=True,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        # ── ① 打开创作者中心 ──
        print("[①/⑤] 打开创作者中心...")
        try:
            page.goto("https://creator.xiaohongshu.com/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception as e:
            print(f"[①/⑤] ⚠️  页面加载超时: {e}")

        time.sleep(3)

        # ── ② 登录检测 ──
        print("[②/⑤] 检查登录状态...")
        if any(k in page.url for k in ["login", "passport", "signin"]):
            print("[②/⑤] ⚠️  未登录，请在浏览器中扫码...")
            try:
                page.wait_for_url(
                    lambda u: not any(k in u for k in ["login", "passport", "signin"]),
                    timeout=120000
                )
                print("[②/⑤] ✅ 登录成功")
                time.sleep(3)
                page.wait_for_load_state("networkidle", timeout=30000)
            except:
                print("[②/⑤] ❌ 登录超时，请重试")
                context.close()
                sys.exit(1)
        else:
            print("[②/⑤] ✅ 已登录")

        # ── ③ 导航到数据中心 ──
        print("[③/⑤] 导航到数据中心...")
        nav_clicked = False
        for sel in [
            "a:has-text('数据中心')",
            "span:has-text('数据中心')",
            "text=数据中心",
            "[class*='sidebar'] text=数据",
            "[class*='nav'] text=数据",
            "li:has-text('数据')",
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    print(f"[③/⑤] ✅ 点击了「{sel}」")
                    nav_clicked = True
                    break
            except:
                continue

        if not nav_clicked:
            print("[③/⑤] ⚠️  未找到侧边栏导航，尝试直接访问URL...")
            try:
                page.goto("https://creator.xiaohongshu.com/creator/analytics", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=15000)
                print("[③/⑤] ✅ URL跳转成功")
            except Exception as e:
                print(f"[③/⑤] ⚠️  URL跳转失败: {e}")

        time.sleep(4)

        # ── ④ 切换到内容数据 ──
        print("[④/⑤] 切换到笔记数据Tab...")
        tab_clicked = False
        for sel in [
            "text=笔记数据",
            "text=内容数据",
            "text=内容概览",
            "[role='tab']:has-text('笔记')",
            "[role='tab']:has-text('内容')",
            "a:has-text('笔记')",
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    print(f"[④/⑤] ✅ 点击了「{sel}」")
                    tab_clicked = True
                    break
            except:
                continue

        if not tab_clicked:
            print("[④/⑤] ⚠️  未找到Tab，可能已在笔记数据页，继续...")

        time.sleep(3)

        # ── ⑤ 点击导出 ──
        print("[⑤/⑤] 查找并点击导出按钮...")
        export_clicked = False
        for sel in [
            "button:has-text('导出')",
            "text=导出数据",
            "text=下载明细",
            "button:has-text('下载')",
            "span:has-text('导出')",
            "[class*='export']",
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    print(f"[⑤/⑤] ✅ 点击了「{sel}」")
                    export_clicked = True
                    break
            except:
                continue

        if not export_clicked:
            print("[⑤/⑤] ⚠️  未找到导出按钮")
            print("[⑤/⑤] 👉 请在浏览器中手动点击导出按钮")
            print("[⑤/⑤] 👉 脚本持续监听下载文件...")

        # 确认弹窗
        time.sleep(2)
        for sel in ["button:has-text('确认')", "button:has-text('确定')", "text=确认导出"]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    print(f"[⑤/⑤] ✅ 已确认导出弹窗")
                    break
            except:
                pass

        # ── ⑥ 等待下载 ──
        print("[等待] 正在等待 Excel 文件下载...")
        print("[等待] 如长时间未响应，请在浏览器中手动操作")
        for i in range(300):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DOWNLOAD_DIR, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                time.sleep(3)
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                size = os.path.getsize(f)
                if size > 500:
                    print(f"[等待] ✅ 下载完成: {os.path.basename(f)} ({size}字节)")
                    context.close()
                    print(f"EXPORT_FILE:{f}")
                    return
                else:
                    print(f"[等待] ⚠️  文件太小({size}字节)，等待写入...")

            if i > 0 and i % 60 == 0:
                print(f"[等待] 已等待 {i//60} 分钟，请检查浏览器...")

        print("[等待] ❌ 超时（5分钟），未检测到下载文件")
        print("[等待] 👉 请手动下载后重新点击复盘按钮")
        context.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
