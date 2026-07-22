#!/usr/bin/env python3
"""小红书全自动导出——按钮全景扫描→精准点击"""

import warnings; warnings.filterwarnings("ignore")
import os, sys, time, glob, json
from playwright.sync_api import sync_playwright

UD = os.path.expanduser("~/.xhs_playwright_profile")
DL = os.path.expanduser("~/Downloads")

def main():
    for f in ["SingletonLock","SingletonCookie","SingletonSocket","lockfile"]:
        p = os.path.join(UD, f);
        if os.path.exists(p): os.remove(p)
    os.makedirs(UD, exist_ok=True)
    start_time = time.time()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            UD, headless=False, accept_downloads=True,
            viewport={"width":1280,"height":800}, locale="zh-CN")
        pg = ctx.new_page()

        # 监听下载，记录所有下载
        downloads = []  # 改为列表，记录每次下载
        def on_download(download):
            fname = os.path.join(DL, download.suggested_filename)
            download.save_as(fname)
            downloads.append(fname)
            print(f"[下载] #{len(downloads)} {download.suggested_filename}")
        pg.on("download", on_download)
        dl_count_before = 0  # 追踪导出前的下载次数

        # ①② 打开+登录
        print("[1] 创作者中心")
        pg.goto("https://creator.xiaohongshu.com/", timeout=30000)
        pg.wait_for_load_state("domcontentloaded"); time.sleep(4)
        if any(k in pg.url for k in ["login","passport","signin"]):
            print("[2] ⏳ 扫码登录...")
            pg.wait_for_url(lambda u: not any(k in u for k in ["login","passport","signin"]), timeout=120000)
            print("[2] ✅"); time.sleep(4)
        else:
            print("[2] ✅ 已登录")
        pg.wait_for_load_state("domcontentloaded"); time.sleep(3)

        # ③④ 导航
        print("[3] 数据看板")
        try: pg.locator("text=数据看板").first.click(timeout=8000)
        except: pg.locator("text=数据").first.click(timeout=5000)
        time.sleep(4); pg.wait_for_load_state("domcontentloaded")

        print("[4] 内容分析")
        try: pg.locator("text=内容分析").first.click(timeout=8000)
        except: pg.locator("text=内容").first.click(timeout=5000)
        time.sleep(6); pg.wait_for_load_state("domcontentloaded")

        # ⑤ 全属性扫描
        print("[5] 扫描页面所有交互元素...")
        btns = pg.evaluate("""() => {
            const r = [];
            document.querySelectorAll('button, [role="button"], a, span, div, img').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width < 10 || rect.height < 10) return;
                const txt = (el.textContent||'').trim();
                r.push({
                    tag:el.tagName,
                    text:txt.slice(0,40),
                    class:(el.className||'').slice(0,60),
                    aria:el.getAttribute('aria-label')||'',
                    title:el.title||'',
                    id:el.id||'',
                    w:Math.round(rect.width),h:Math.round(rect.height),
                    x:Math.round(rect.x),y:Math.round(rect.y),
                });
            });
            return r;
        }""")
        with open("/tmp/xhs_buttons.json","w") as f:
            json.dump(btns, f, indent=2, ensure_ascii=False)
        print(f"[5] {len(btns)}个元素 → /tmp/xhs_buttons.json")
        # 打印可能相关的
        for b in btns:
            low = (b['text']+b['aria']+b['title']+b['class']+b['id']).lower()
            if any(k in low for k in ['export','导出','下载','download','报表']):
                print(f"  ⚡ {b['tag']} text={b['text']} aria={b['aria']} class={b['class'][:30]}")

        # ⑥ 点击导出
        print("[6] 点击导出...")
        sel_list = [
            '[aria-label*="导出"]','[aria-label*="下载"]','[aria-label*="export"]','[aria-label*="download"]',
            '[title*="导出"]','[title*="下载"]','[title*="export"]',
            'text=导出数据','text=下载明细','text=导出','text=下载',
            'button:has-text("导出")','button:has-text("下载")',
            '[class*="export"]','[class*="download"]',
        ]
        ok = False
        for s in sel_list:
            try:
                el = pg.locator(s).first
                if el.is_visible(timeout=2000):
                    el.click(); print(f"[6] ✅ {s}"); ok=True; break
            except: pass

        if not ok:
            # 暴力点：找所有按钮里那个最像导出的
            for b in btns:
                if b['tag']=='BUTTON' and b['w']<300 and b['h']<80 and b['text'] not in ['','发布','取消']:
                    low = (b['text']+b['aria']+b['title']).lower()
                    if any(k in low for k in ['export','导出','下载','download']):
                        try:
                            pg.locator(f"text={b['text']}").first.click(timeout=2000)
                            print(f"[6] 🎯 {b['text']}"); ok=True; break
                        except: pass
        if not ok:
            print("[6] ❌ 未找到导出按钮"); pg.screenshot(path="/tmp/xhs_fail.png"); print("[6] 📸 /tmp/xhs_fail.png")

        # ⑦ 确认弹窗/导出面板
        time.sleep(2)
        dl_count_before = len(downloads)  # 记录点击导出前的下载计数
        confirm_ok = False
        for t in ["确认", "确定", "导出", "下载", "确认导出"]:
            try:
                el = pg.get_by_text(t).first
                if el.is_visible(timeout=2000):
                    el.click()
                    print(f"[7] ✅ 点击了「{t}」")
                    confirm_ok = True
                    break
            except: pass
        if not confirm_ok:
            print("[7] 无确认弹窗（可能直接下载）")

        # ⑧ 等真正的下载（只取确认弹窗之后下载的文件，且验证是Excel）
        print("[8] ⏳ 等待正式下载（跳过导出前的无效文件）...")
        for i in range(300):
            time.sleep(1)
            # 只取确认后新下载的文件
            new_downloads = downloads[dl_count_before:]
            for f in new_downloads:
                if os.path.exists(f):
                    size = os.path.getsize(f)
                    # 验证是真正的Excel（文件头: PK\x03\x04 表示xlsx）
                    with open(f, "rb") as fh:
                        header = fh.read(4)
                    if header == b"PK\x03\x04":
                        print(f"[8] ✅ 有效Excel {os.path.basename(f)} ({size}字节)")
                        ctx.close()
                        print(f"EXPORT_FILE:{f}"); return
                    else:
                        print(f"[8] ⚠️  跳过无效文件 {os.path.basename(f)} (非Excel格式, 文件头:{header.hex()})")
            # 也扫描文件系统
            files = sorted(glob.glob(os.path.join(DL,"笔记列表明细表*.xlsx")),key=os.path.getmtime,reverse=True)
            if files:
                f = files[0]
                if os.path.getmtime(f) > start_time and os.path.getsize(f) > 3000:
                    with open(f, "rb") as fh:
                        header = fh.read(4)
                    if header == b"PK\x03\x04":
                        print(f"[8] ✅ (扫描) {os.path.basename(f)}"); ctx.close()
                        print(f"EXPORT_FILE:{f}"); return
            if i==120: print(f"[8] ⏳ 2分钟了，还在等...")
        print("[8] ❌ 超时"); ctx.close(); sys.exit(1)

if __name__=="__main__":main()
