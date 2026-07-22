#!/usr/bin/env python3
"""小红书全自动导出——文字定位+点击链+文件检测"""

import warnings; warnings.filterwarnings("ignore")
import os, sys, time, glob
from playwright.sync_api import sync_playwright

UD = os.path.expanduser("~/.xhs_playwright_profile")
DL = os.path.expanduser("~/Downloads")

def step(page, n, msg, fn):
    """执行一步，打印状态，出错不崩"""
    try:
        fn()
        print(f"[{n}] ✅ {msg}")
        return True
    except Exception as e:
        print(f"[{n}] ⚠️ {msg}: {str(e)[:60]}")
        return False

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
        pg = ctx.new_page()

        # ① 打开创作者中心
        step(pg, 1, "打开创作者中心",
             lambda: pg.goto("https://creator.xiaohongshu.com/", timeout=30000))
        pg.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        # ② 登录
        if any(k in pg.url for k in ["login","passport","signin"]):
            print("[2] ⏳ 请扫码登录...")
            try:
                pg.wait_for_url(lambda u: not any(k in u for k in ["login","passport","signin"]), timeout=120000)
                print("[2] ✅ 登录成功")
                time.sleep(4)
                pg.wait_for_load_state("domcontentloaded")
            except:
                print("[2] ❌ 登录超时"); ctx.close(); sys.exit(1)
        else:
            print("[2] ✅ 已登录")

        # ③ 扫描页面元素（保存到文件，不受stdout截断影响）
        print("[3] 🔍 扫描页面可点击元素 → /tmp/xhs_elements.txt")
        try:
            items = pg.evaluate("""() => {
                const found = [];
                document.querySelectorAll('a, button, span, div, li, [role="button"], [class*="btn"]').forEach(el => {
                    const text = (el.textContent || '').trim().slice(0,40);
                    if (text && text.length < 30 && text.length > 1) {
                        found.push(text);
                    }
                });
                return [...new Set(found)].sort();
            }""")
            with open("/tmp/xhs_elements.txt", "w") as f:
                for t in items:
                    f.write(t + "\n")
            print(f"   找到 {len(items)} 个可点击文本")
        except Exception as e:
            print(f"   扫描失败: {e}")

        # ④ 点击「数据中心」
        time.sleep(3)
        clicked = step(pg, 4, "点击「数据中心」", lambda: pg.get_by_text("数据中心", exact=True).first.click(timeout=8000))
        if not clicked:
            clicked = step(pg, 4, "点击数据(模糊)", lambda: pg.locator("text=数据").first.click(timeout=5000))
        if clicked:
            time.sleep(4)
            pg.wait_for_load_state("domcontentloaded")
        else:
            print("[4] ⚠️ 手动点击数据中心，脚本继续监听...")

        # ⑤ 点击「笔记数据」Tab
        time.sleep(3)
        tab = step(pg, 5, "点击「笔记数据」",
                   lambda: pg.locator("text=笔记数据").first.click(timeout=5000))
        if not tab:
            step(pg, 5, "点击「内容数据」",
                 lambda: pg.locator("text=内容数据").first.click(timeout=3000))
        time.sleep(5)  # 等笔记数据页面加载完

        # ⑥ 点击「导出」
        for label in ["导出数据", "导出", "下载明细", "下载", "下载数据", "数据导出", "报表导出"]:
            if step(pg, 6, f"点击「{label}」",
                    lambda: pg.get_by_text(label).first.click(timeout=4000)):
                break
        else:
            print("[6] ⚠️ 请手动点击导出按钮")
            pg.screenshot(path="/tmp/xhs_export_page.png")
            print("[6] 📸 截图: /tmp/xhs_export_page.png")

        # ⑦ 确认弹窗
        time.sleep(2)
        for label in ["确认", "确定"]:
            try:
                btn = pg.get_by_text(label).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"[7] ✅ 已确认「{label}」")
                    break
            except:
                pass

        # ⑧ 等待文件下载
        print("[8] ⏳ 等待下载...")
        for i in range(300):
            time.sleep(1)
            after = set(glob.glob(os.path.join(DL, "笔记列表明细表*.xlsx")))
            new = after - before
            if new:
                time.sleep(3)
                f = sorted(new, key=os.path.getmtime, reverse=True)[0]
                if os.path.getsize(f) > 500:
                    print(f"[8] ✅ {os.path.basename(f)} ({os.path.getsize(f)}字节)")
                    ctx.close()
                    print(f"EXPORT_FILE:{f}")
                    return
            if i > 0 and i % 60 == 0:
                print(f"[8] ⏳ 已等{i//60}分钟...")
        print("[8] ❌ 超时")
        ctx.close(); sys.exit(1)

if __name__ == "__main__":
    main()
