#!/bin/bash
# 周度复盘一键：读已有数据 → 生成报告 → 打开文件

echo "📊 周度数据复盘"
echo "==========================="

# 先跑浏览器导出（后台，不阻塞）
python3 "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/export_xhs_data.py" &>/dev/null &

# 前台直接生成报告
REVIEW_OUT=$(python3 "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/weekly_review.py" 2>/dev/null)
echo "$REVIEW_OUT" | grep -v "^FILE:"

REPORT_FILE=$(echo "$REVIEW_OUT" | grep "^FILE:" | cut -d: -f2-)
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
    echo ""
    open "$REPORT_FILE" -a Obsidian
    echo "✅ 报告已打开 | 浏览器后台导出数据中..."
else
    echo "❌ 报告生成失败"
fi
