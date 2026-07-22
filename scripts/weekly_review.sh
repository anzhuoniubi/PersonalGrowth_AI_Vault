#!/bin/bash
# 全自动周度复盘 Pipeline
# 导出数据 → 生成报告 → 打开文件

echo "🔄 全自动周度复盘 Pipeline"
echo "==========================="
echo ""

# Step 1: 导出小红书数据
echo "📥 Step 1/3: 导出数据..."
EXPORT_OUT=$(python3 "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/export_xhs_data.py" 2>/dev/null)
echo "$EXPORT_OUT"

# 检查是否导出成功
EXPORT_FILE=$(echo "$EXPORT_OUT" | grep "^EXPORT_FILE:" | cut -d: -f2-)
if [ -z "$EXPORT_FILE" ]; then
    # 导出失败或需手动操作，直接用已有数据
    echo ""
    echo "⚠️  自动导出未完成，使用已有数据文件..."
else
    echo "✅ 新数据: $(basename "$EXPORT_FILE")"
fi

echo ""

# Step 2: 生成复盘报告
echo "📊 Step 2/3: 生成复盘报告..."
REVIEW_OUT=$(python3 "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/scripts/weekly_review.py" 2>/dev/null)
echo "$REVIEW_OUT" | grep -v "^FILE:"

# Step 3: 打开报告
REPORT_FILE=$(echo "$REVIEW_OUT" | grep "^FILE:" | cut -d: -f2-)
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
    echo ""
    echo "📄 Step 3/3: 打开报告..."
    open "$REPORT_FILE" -a Obsidian
    echo "✅ 全流程完成！"
else
    echo ""
    echo "❌ 报告生成失败"
fi
