---
created: 2026-07-20
tags: [gstack, 工具, 技能, 集成, 使用说明]
aliases: [gstack使用指南, gstack技能手册]
---

# gstack 使用说明

> gstack 是 YC CEO Garry Tan 开发的开源技能集（MIT 协议），提供了 50+ 个 AI 辅助开发技能。
> 本系统从中精选并接入了 4 个核心技能，适配到内容创作流程中。
>
> 官方仓库：https://github.com/garrytan/gstack

---

## 已集成的 4 个技能

### 1. `/gstack-office-hours`
**用于：选题Agent — 每日选题前的战略校准**

在选题评分之前，先回答 Garry Tan 的 6 个强制问题，避免做无效选题。

**什么时候调用：**
- 每日选题前（Step 0）
- 当一个选题感觉"可以写但不确定"时

**典型的输出：**
- 这个选题真正在解决的问题是什么
- 目标用户此刻需要这个内容吗
- 它与品牌定位的匹配度判断

**在我的系统中的位置：**
> [[agents/topic_agent]] → 日度选题流程 → Step 0: 战略校准

---

### 2. `/gstack-plan-ceo-review`
**用于：CEO Agent — 季度/重大决策时的战略审视**

提供 CEO 视角的审视框架——"这件事的 10 倍好版本是什么？""我们是不是在做正确的事？"

**什么时候调用：**
- 每季度品牌定位评估时
- 当考虑重大的内容方向调整时
- 当系统需要做取舍决策时

**典型的输出：**
- 对现有策略的批判性审视
- 从"10 倍好"角度提出的方向建议
- 资源分配的优先级建议

**在我的系统中的位置：**
> [[agents/ceo_agent]] → 每季度 → 品牌定位评估

---

### 3. `/gstack-retro`
**用于：复盘Agent — 周度结构化回顾**

比现有复盘模板多一个纬度：不只是"数据怎么样"，而是"我们学到了什么""下次可以改进什么"。

**什么时候调用：**
- 每周日周度复盘报告生成时
- 一个重点内容系列完结后

**典型的输出：**
- 本周 What went well / What didn't
- 提炼出的经验教训
- 具体的改进行动项

**在我的系统中的位置：**
> [[agents/review_agent]] → 每周 → 周度复盘报告

---

### 4. `/gstack-investigate`
**用于：复盘Agent — 数据异常时根因诊断**

当某项数据（互动率、曝光量、涨粉）出现无法凭经验解释的波动时，进行系统性诊断。

**什么时候调用：**
- 互动率突然腰斩
- 某篇内容曝光远低于预期
- 连续 3 篇互动持续走低

**典型的输出：**
- 问题根因分析（平台侧 vs 内容侧 vs 时机侧）
- 验证假设的方法（A/B测试方案）
- 具体修复建议

**在我的系统中的位置：**
> [[agents/review_agent]] → 数据异常诊断

---

## 使用方式

### 对话中直接调用

当你在对话中需要这些能力时，直接输入 slash 命令即可：

```
/gstack-office-hours — 选题前战略校准
/gstack-plan-ceo-review — 战略审视
/gstack-retro — 结构化回顾
/gstack-investigate — 根因诊断
```

### 在 Agent 工作流中自动触发

这些技能已写入对应的 Agent 配置，内容生产流程中会在正确时机自动建议调用：

```
选题前 → topic_agent 建议调用 office-hours
周复盘 → review_agent 自动调用 retro
数据异常 → review_agent 自动建议调用 investigate
季度评估 → ceo_agent 自动调用 plan-ceo-review
```

---

## 未集成的 gstack 技能（仅供参考）

gstack 还有大量软件工程专用的技能，与本系统不直接相关，但以下几个可在极少数场景按需使用：

| 技能 | 用途 | 可能会用到的场景 |
|------|------|----------------|
| `/gstack-diagram` | 生成 Mermaid 图表 | 需要往知识体系中画流程图/关系图时 |
| `/gstack-browse` | 浏览器自动化 | 需要做复杂网页研究时（已有 WebFetch 和 Agent-Reach 兜底） |
| `/gstack-document-generate` | 自动生成文档 | 需要快速建立文档框架时 |
| `/gstack-make-pdf` | Markdown 转 PDF | 需要把笔记导出为 PDF 分享时 |

---

## 注意事项

1. **gstack 是独立维护的开源项目**，与本系统的 Agent/Skill 体系是平行关系，不冲突
2. 如果 gstack 升级，运行 `cd ~/.claude/skills/gstack && git pull && ./setup` 即可更新
3. 本系统已保留完整的品牌专有 Agent 和 Skill——gstack 只补充了 4 个特定的流程增强点，不影响系统原有架构

---

*集成日期：2026-07-20 | 版本：v1.0*
*关联知识：[[01_个人定位/半醒之间IP定位]]*
