# 内容生产工作流（半醒之间版）

> 从选题到发布再到复盘的内容生产全流程。
> 适用于：每日内容创作。
> 对齐定位：[[01_个人定位/半醒之间IP定位.md|半醒之间IP定位]] · [[06_知识体系/三层内容体系参考.md|三层内容体系]]

---

```yaml
name: 内容生产工作流（半醒之间版）
trigger: Creator 输入一个主题 / 选题Agent 输出选题
频率: 每日
预估耗时: 35-50 分钟
```

## 流程步骤（Step 0-11）

### Step 0: 内容层定位
**执行 Agent**: CEO Agent / Creator
**判断**: 这个选题属于哪个内容层？
- 🔍 **觉察层**："我为什么活得不像自己？" → 共鸣驱动
- 🔄 **重构层**："AI 时代我还能怎么办？" → 认知驱动
- 🛠️ **创造层**："如何把自己变成价值？" → 行动驱动
**输出**: 内容层标注 → 后续所有步骤按该层调整语气和结构
**预计耗时**: 1 分钟

### Step 1: 用户分析
**执行 Agent**: [[agents/research_agent.md|Research Agent]]
**调用 Skill**: [[skills/research/用户痛点挖掘.md|用户痛点挖掘]]
**输入**: 主题 + 当前用户画像 → [[02_用户研究/核心用户画像.md|核心用户画像]]
**输出**: 用户洞察卡片 → 保存到 `02_用户研究/`
**预计耗时**: 3 分钟

### Step 2: 选题优化 & 三层校准
**执行 Agent**: [[agents/topic_agent.md|Topic Agent]]
**调用 Skill**: [[skills/strategy/赛道分析.md|赛道分析]]
**输入**: 主题 + 热点数据 + 爆款参考 + 三层标注
**输出**: 选题评分卡（含三层对标） → 保存到 [[03_选题库/选题卡片模板.md|03_选题库]]
**检查**: 当前选题池各层比例是否合理？具体比例以 [[10_数据复盘/90天实验计划.md|90天实验计划]] 为准。
**预计耗时**: 3 分钟

### Step 3: 爆款参考
**执行 Agent**: [[agents/topic_agent.md|Topic Agent]] / [[agents/viral_analysis_agent.md|Viral Analysis Agent]]
**调用 Skill**: [[skills/data/爆款拆解.md|爆款拆解]]
**输入**: 同类爆款内容 URL
**输出**: 爆款拆解报告 → 保存到 [[04_爆款拆解库/爆款拆解模板.md|04_爆款拆解库]]
**预计耗时**: 5 分钟

### Step 4: 内容撰写
**执行 Agent**: [[agents/content_agent.md|Content Agent]]
**调用 Skill**: [[skills/content/标题生成.md|标题生成]] · [[skills/content/金句生成.md|金句生成]] · [[skills/redbook-writing/SKILL.md|redbook-writing]]
**输入**: 选题 + 标题方案 + 内容层标注
**原则**:
- **先解决痛苦，再升维**
- **三层语气适配**：觉察层温柔共鸣 / 重构层理性启发 / 创造层真实记录
- **探索者语气**：不是"我教你"，是"我在做，你看"
**输出**: 完整正文 + 标题 + 标签 + 金句
**预计耗时**: 10 分钟

### Step 5: 生成渲染 Markdown
**执行 Agent**: [[agents/content_agent.md|Content Agent]]
**调用 Skill**: [[skills/content/小红书文案写作.md|小红书文案写作]]
**操作**: 将正文转换为渲染专用 Markdown（含 frontmatter）
**输出**: `content.md`
**预计耗时**: 2 分钟

### Step 6: 视觉设计
**执行 Agent**: [[agents/visual_agent.md|Visual Agent]]
**调用 Skill**: [[skills/visual/封面设计.md|封面设计]] · [[skills/visual/AI绘图提示词.md|AI绘图提示词]]
**输入**: 已定标题 + 正文核心主张 + 情绪基调 + 内容层
**输出**: 封面方案（含三区布局+配色+字体）+ AI 绘图提示词 → 追加到内容文件
**预计耗时**: 5 分钟

### Step 7: 图片渲染
**执行 Agent**: [[agents/content_agent.md|Content Agent]] / [[agents/visual_agent.md|Visual Agent]]
**调用 Script**: `skills/redbook-auto/scripts/render_xhs.py`
**操作**: 按内容层选主题（觉察-sketch / 重构-default / 创造-botanical），默认 auto-split
**输出**: `cover.png`（封面）+ `card_N.png`（正文卡片）
**预计耗时**: 3 分钟

### Step 8: 保存归档
**执行 Agent**: [[agents/knowledge_base_agent.md|Knowledge Base Agent]]
**输入**: 完整内容包（标题/正文/封面方案/渲染图片引用/金句/标签）
**输出**: 保存到 `05_内容生产库/{YYYY-MM-DD}_{标题}.md`
**归档规范**:
- 文件名：`YYYY-MM-DD_{内容关键词}.md`
- Frontmatter：title / date / status(已发布/待发布/草稿) / source / agent / tags / content_layer
- 正文后依次追加：标题区 → 封面方案 → 正文 → 标签 → 金句 → 敏感词自查 → 审校记录 → 创作说明 → **数据追踪表**（72h 内补充）
- 每次用 Edit 追加，不用 Write 覆盖全文件
**预计耗时**: 2 分钟

### Step 9: Creator 审核
**执行人**: Creator（人类）
**检查项**:
- [ ] 内容真实性：是否有证据/经历支撑
- [ ] 风格一致性：是否符合个人表达风格
- [ ] 渲染效果：封面在小图下是否可读
- [ ] 合规检查：是否违反平台规则
- [ ] 价值判断：是否对目标用户有帮助
**预计耗时**: 5 分钟

### Step 10: 发布 + 互动
**执行人**: Creator + [[agents/content_agent.md|Content Agent]]
**调用 Script**: `skills/redbook-auto/scripts/publish_xhs.py`
**调用 Skill**: [[skills/growth/互动运营.md|互动运营]]
**流程**: 默认仅自己可见 → 确认后 `--public` 公开发布
**输出**: 已发布内容 + 评论区运营模板
**预计耗时**: 5 分钟

### Step 11: 数据追踪
**执行 Agent**: [[agents/review_agent.md|Review Agent]]
**调用 Skill**: [[skills/data/数据分析.md|数据分析]]
**触发**: 发布后 24 小时 + 72 小时
**输出**: 数据追踪记录 → 保存到 [[10_数据复盘/数据看板.md|10_数据复盘/]]
**预计耗时**: 每轮 2 分钟

---

## 检查清单（供 Creator 使用）

### 创作前
- [ ] 我从哪个 Skill 开始？
- [ ] 今天的目标用户群体是谁？
- [ ] 这个选题是否在选题库中评分通过？
- [ ] 核心主张是什么？一句话能说清吗？

### 创作中
- [ ] 是否参考了记忆系统中的品牌和风格指南？
- [ ] 标题是否符合标题公式？字数 ≤20 字？
- [ ] 开头是否有钩子？
- [ ] 正文是否有结构？（SCQA/故事/清单）
- [ ] 金句是否单独提取（≥3 句）？
- [ ] 结尾是否有行动号召？
- [ ] 封面方案是否已确认（构图类型+配色+备选）？

### 发布前
- [ ] 是否经过真实性审核？
- [ ] 封面在小图下是否可读？3 秒能理解主张？
- [ ] 敏感词自查是否完成？
- [ ] 审校记录是否完整？
- [ ] 标签是否覆盖核心关键词？
- [ ] 是否准备了互动回复模板？

### 发布后
- [ ] 是否更新了选题库状态（已发布+勾选数据复盘待做）？
- [ ] 是否在 1 小时内回复评论？
- [ ] 24h 数据是否已填入数据追踪表？
- [ ] 72h 复盘是否在窗口期内完成？
- [ ] GEPA 数据集是否已追加记录？
- [ ] 周报中是否包含这篇内容？

---

## 产出物存档规范

```
05_内容生产库/{YYYY-MM-DD}_{内容标题}.md
```

### 文件模板
```markdown
---
title: ""
date: {YYYY-MM-DD}
status: "已发布/待发布/草稿"
source: "选题卡片路径"
agent: "Content Agent → Visual Agent"
tags: []
content_layer: "觉察层/重构层/创造层"
primary_job: "feed_stop/search_answer/explain/..."
truth_label: "真实/授权改编/虚构"
---

== 标题 ==
**主标题**（字数 ✅）
备选标题列表

== 封面方案 ==
**调用 Skill：** [[skills/visual/封面设计.md|封面设计]] · [[skills/visual/AI绘图提示词.md|AI绘图提示词]]

### Step 1：内容分析
| 维度 | 提取 |
|------|------|
| 核心表达点 | |
| 内容类型 | |
| 情绪基调 | |

### Step 2：选择构图 → 类型
### Step 3：三区布局
### Step 4：配色
### Step 5：AI 绘图提示词
### Step 6：小图测试
### 备选方案（纯文字排版）

== 正文 ==

== 标签 ==

== 金句提取 ==

== 敏感词自查 ==

== 审校记录 ==
compliance_review: PASS/PARTIAL/FAIL
creative_review: PASS/PARTIAL/FAIL

== 创作说明 ==

== 数据追踪 ==（72h 内补充）
```

---

## 上下游连接

### 上游输入
- [[03_选题库/前30篇选题矩阵.md|选题库]] 中已评分通过的选题
- [[02_用户研究/核心用户画像.md|核心用户画像]]
- [[memory/content_style|content_style]] 风格指南

### 下游输出
- 发布后的笔记
- [[05_内容生产库/]] 归档内容
- [[10_数据复盘/数据看板.md|数据看板]] 追踪数据
- GEPA 数据集记录

---

> **版本**：v2.1  
> **最后更新**：2026-07-22  
> **父文档**：[[CLAUDE.md]] · [[SYSTEM_ARCHITECTURE.md]]
