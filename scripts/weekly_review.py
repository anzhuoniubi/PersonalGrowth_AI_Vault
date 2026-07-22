#!/usr/bin/env python3
"""周度数据复盘脚本 —— 读取最新Excel，输出简洁速报"""

import warnings
warnings.filterwarnings("ignore")

import openpyxl, glob, os, json

files = sorted(glob.glob(os.path.expanduser('~/Downloads/笔记列表明细表*.xlsx')), key=os.path.getmtime, reverse=True)

if not files:
    print("❌ 未找到数据文件，请从创作者中心导出笔记列表明细表到下载目录")
    exit(1)

wb = openpyxl.load_workbook(files[0], data_only=True)
ws = wb[wb.sheetnames[0]]
rows = list(ws.iter_rows(values_only=True))

header = f"📊 周度数据速报 | {os.path.basename(files[0])}"
print(header)
print("=" * 50)

total_exp = 0
total_interaction = 0
count = 0

for r in rows[2:]:
    if r[0] and int(r[3] or 0) > 0:
        title = str(r[0])[:28]
        exp = int(r[3] or 0)
        views = int(r[4] or 0)
        likes = int(r[6] or 0)
        comments = int(r[7] or 0)
        saves = int(r[8] or 0)
        shares = int(r[10] or 0)
        ctr = float(r[5] or 0)
        interaction = likes + comments + saves + shares
        rate = round(interaction / max(views, 1) * 100, 1)
        flag = '🔥' if exp > 10000 else ('✅' if exp > 1000 else '⚡')
        print(f'{flag} {title}')
        print(f'   曝光:{exp}  CTR:{ctr}  互动:{interaction}  互动率:{rate}%')
        total_exp += exp
        total_interaction += interaction
        count += 1

print("=" * 50)
print(f"💡 总计 {count} 篇 | 总曝光: {total_exp} | 总互动: {total_interaction}")

# Find top performer
top = max(
    [(int(r[3] or 0), str(r[0])[:20], int(r[4] or 0)) for r in rows[2:] if r[0] and int(r[3] or 0) > 0],
    default=(0, "N/A", 0)
)
print(f"🔥 Top: {top[1]} (曝光:{top[0]}, 观看:{top[2]})")
