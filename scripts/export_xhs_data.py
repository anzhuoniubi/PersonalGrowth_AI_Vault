#!/usr/bin/env python3
"""小红书全自动导出——稳健版"""

import warnings; warnings.filterwarnings("ignore")
import os, sys, time, glob
from playwright.sync_api import sync_playwright

UD = os.path.expanduser("~/.xhs_playwright_profile")
DL = os.path.expanduser("~/Downloads")

def main():
    for f in ["SingletonLock","SingletonCookie","SingletonSocket","lockfile"]:
        p = os.path.join(UD, f);
        if os.path.exists(p): os.remove(p)
    os.makedirs(UD, exist_ok=True)

    start = time.time()
    downloads = []

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            UD, headless=False, accept_downloads=True,
            viewport={"width":1280,"height":800}, locale="zh-CN")
        pg = ctx.new_page()

        def on_dl(d):
            try:
                f = os.path.join(DL, d.suggested_filename)
                d.save_as(f)
                downloads.append(f)
                print(f"[下载] {d.suggested_filename}")
            except Exception as e:
                print(f"[下载] ⚠️ 保存失败: {e}")
        pg.on("download", on_dl)

        # ① 打开
        pg.goto("https://creator.xiaohongshu.com/", timeout=30000)
        pg.wait_for_load_state("domcontentloaded"); time.sleep(4)

        # ② 登录
        if any(k in pg.url for k in ["login","passport","signin"]):
            print("[2] ⏳ 扫码...")
            pg.wait_for_url(lambda u: not any(k in u for k in ["login","passport","signin"]), timeout=120000)
            time.sleep(4)
        pg.wait_for_load_state("domcontentloaded"); time.sleep(3)

        # ③④ 导航
        for label in ["数据看板", "内容分析"]:
            try:
                pg.locator(f"text={label}").first.click(timeout=8000)
                time.sleep(4)
                pg.wait_for_load_state("domcontentloaded")
            except:
                pg.locator("text=数据").first.click(timeout=5000)

        # ⑤ 导出
        try:
            pg.locator("text=导出数据").first.click(timeout=8000)
        except:
            pass
        time.sleep(3)

        # ⑥ 确认
        for t in ["确认导出", "导出", "确认", "确定", "下载"]:
            try:
                el = pg.get_by_text(t).first
                if el.is_visible(timeout=3000):
                    el.click(); break
            except: pass

        # ⑦ 等真实Excel下载
        for _ in range(300):
            time.sleep(1)
            for i, f in reversed(list(enumerate(downloads))):
                if os.path.exists(f) and os.path.getsize(f) > 3000:
                    try:
                        with open(f, "rb") as fh:
                            if fh.read(4) == b"PK\x03\x04":
                                print(f"✅ {os.path.basename(f)} ({os.path.getsize(f)}B)")
                                time.sleep(1)
                                ctx.close()
                                print(f"EXPORT_FILE:{f}")
                                return
                    except: pass

        ctx.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
