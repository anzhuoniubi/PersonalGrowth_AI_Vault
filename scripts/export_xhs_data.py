#!/usr/bin/env python3
"""小红书全自动导出——基于真实页面扫描结果"""

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
    before = set(glob.glob(os.path.join(DL, "笔记列表明细表*.xlsx")))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            UD, headless=False, accept_downloads=True,
            viewport={"width":1280,"height":800}, locale="zh-CN")
        pg = ctx.new_page()

        # ① 打开
        print("[1] 创作者中心")
        pg.goto("https://creator.xiaohongshu.com/", timeout=30000)
        pg.wait_for_load_state("domcontentloaded"); time.sleep(4)

        # ② 登录
        if any(k in pg.url for k in ["login","passport","signin"]):
            print("[2] ⏳ 请扫码...")
            pg.wait_for_url(lambda u: not any(k in u for k in ["login","passport","signin"]), timeout=120000)
            print("[2] ✅")
            time.sleep(4); pg.wait_for_load_state("domcontentloaded")
        else:
            print("[2] ✅ 已登录")

        # ③ 点击「数据看板」（页面真实文字）
        print("[3] 点击「数据看板」")
        try:
            pg.locator("text=数据看板").first.click(timeout=8000)
        except:
            pg.locator("text=数据").first.click(timeout=5000)
        time.sleep(4)
        pg.wait_for_load_state("domcontentloaded")

        # ④ 点击「内容分析」
        print("[4] 点击「内容分析」")
        try:
            pg.locator("text=内容分析").first.click(timeout=8000)
        except:
            pg.locator("text=内容").first.click(timeout=5000)
        time.sleep(5)
        pg.wait_for_load_state("domcontentloaded")

        # ⑤ 点击「笔记数据总览」或其Tab
        print("[5] 切到笔记数据")
        try:
            pg.locator("text=笔记数据总览").first.click(timeout=5000)
        except:
            pg.locator("text=笔记").first.click(timeout=3000)
        time.sleep(5)

        # ⑥ 找导出按钮（图标+文字+属性全方位）
        print("[6] 查找导出按钮...")
        clicked = False
        selectors = [
            # 图标按钮
            '[class*="export"]', '[class*="download"]',
            'button[class*="export"]', 'button[class*="download"]',
            # aria-label
            '[aria-label*="导出"]', '[aria-label*="下载"]',
            '[aria-label*="export"]', '[aria-label*="download"]',
            # title属性
            '[title*="导出"]', '[title*="下载"]',
            # SVG图标常见结构
            'button:has(svg)', '[role="button"]:has(svg)',
            # 兜底：所有按钮
            'button',
        ]
        for sel in selectors:
            try:
                btn = pg.locator(sel).first
                if btn.is_visible(timeout=2000):
                    text = btn.text_content() or ""
                    # 跳过明显不是导出的大按钮
                    if len(text) > 10 and "发布" in text: continue
                    btn.click()
                    print(f"[6] ✅ {sel} (text:{text[:20]})")
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            print("[6] ⚠️ 未找到导出按钮，请手动点击")
            pg.screenshot(path="/tmp/xhs_export_page.png")
            print("[6] 📸 截图已保存")

        # ⑦ 确认弹窗
        time.sleep(2)
        for t in ["确认", "确定"]:
            try:
                btn = pg.get_by_text(t).first
                if btn.is_visible(timeout=2000):
                    btn.click(); print(f"[7] ✅ 已确认")
                    break
            except: pass

        # ⑧ 等下载
        print("[8] ⏳ 等待下载...")
        for i in range(300):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DL, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                time.sleep(3)
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                if os.path.getsize(f) > 500:
                    print(f"[8] ✅ {os.path.basename(f)}")
                    ctx.close()
                    print(f"EXPORT_FILE:{f}")
                    return
            if i > 0 and i % 60 == 0:
                print(f"[8] ⏳ {i//60}分钟...")
        print("[8] ❌ 超时"); ctx.close(); sys.exit(1)

if __name__ == "__main__":
    main()
