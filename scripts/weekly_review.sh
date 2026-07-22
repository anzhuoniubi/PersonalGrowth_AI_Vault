#!/bin/bash
# 全自动周度复盘 Pipeline（顺序执行，所有输出可见）

echo "╔══════════════════════════════╗"
echo "║  📊 半醒之间 · 周度复盘     ║"
echo "╚══════════════════════════════╝"
echo ""

# ── Step 1: 导出数据 ──
echo "📥 Step 1/2: 导出小红书数据"
echo "──────────────────────────────"
python3 -u "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/export_xhs_data.py"
EXPORT_EXIT=$?

if [ $EXPORT_EXIT -ne 0 ]; then
    echo ""
    echo "⚠️  自动导出未完成 (exit:$EXPORT_EXIT)"
    echo "   将使用已有数据继续..."
fi

echo ""
echo "──────────────────────────────"

# ── Step 2: 生成复盘报告 ──
echo "📊 Step 2/2: 生成复盘报告"
REVIEW_OUT=$(python3 -u "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/weekly_review.py" 2>/dev/null)
echo "$REVIEW_OUT" | grep -v "^FILE:"

REPORT_FILE=$(echo "$REVIEW_OUT" | grep "^FILE:" | cut -d: -f2-)
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
    echo ""
    echo "📄 打开复盘报告..."
    open "$REPORT_FILE" -a Obsidian
    echo "✅ 完成！"
    exit 0
else
    echo "❌ 未找到数据文件。请先导出 Excel 到:「~/Downloads/笔记列表明细表.xlsx」"
    exit 1
fi
