# 一次性审美探索 Prompt

这份资产解决一个窄问题：当 exact published style binding 尚不存在，但真实素材、任务和载体已经明确时，怎样先做一个不像通用 AI PPT 的可查看粗原型。

它不是爆款模板，也不是 starter pack。8 个 prompt 全部固定为 `not_performance_evidence`，其中 7 条可做探索粗原型，AP02 因 observation 不完整暂时只能当 research lead：

```text
candidate_only
not_performance_evidence
output_ceiling <= prototype_only
starter_eligible=false
```

## 与其他资产的分工

```text
traffic mechanism → 为什么停、读、存、评或关注
visual direction card → 证据按什么顺序到达、每页做什么
aesthetic exploration prompt → 无 binding 时，一次性粗原型怎样避免通用 PPT
published style binding → 最终颜色、字形、裁切、密度、标注和图像处理
```

一旦存在 exact published binding，审美 prompt 自动禁用。不能把 overlay 和 binding 混合后声称“既有证据又更好看”。

## 8 个方向

| ID | 一次性方向 | 典型任务 | 核心不是 |
| --- | --- | --- | --- |
| AP01 | 真实工作物先行 | 软件教程、法律清单、产品比较、政策解释 | 给截图/文件套企业海报 |
| AP02 | 真实质地占满画面（research lead） | 美妆质地比较 | 用不完整观察生成原型 |
| AP03 | 单一真实场景只做在场锚点 | 体验引出的关系/生活观点 | 氛围图替观点作证 |
| AP04 | 跨时间档案保留差异 | 关系、成长、长期项目 | 统一电影滤镜 |
| AP05 | 正式编辑，不做企业 KV | 法律、政策、复杂解释 | 深蓝渐变等于专业 |
| AP06 | 单命题字卡 + 场景兑现 | 观点、系列代理 | 纯色大字等于流量 |
| AP07 | 聊天界面只承担推进 | 授权聊天、明确虚构演绎 | 伪投稿、伪真人截图 |
| AP08 | 前后变化必须带代价 | 改造、修复、流程优化 | 只有精修 after |

完整 prompt、素材门、禁用项和来源在 `assets/aesthetic-exploration-prompts-v1.json`。可安装 Skill 内同时携带 `aesthetic-source-claims-v1.json` 与 `aesthetic-observation-index-v1.jsonl` 两个带 hash 的运行快照；完整长审计仍在仓库 `docs/research/2026-07-18-aesthetic-prompt-source-audit.md`。公开经验只负责提供候选变量，站内 observation 也未被冒充成第一方流量。

## 选择命令

先用一组已经观察过的 exact scope cell 查询。类目参数使用资产里的 `category_code`，并同时提供 direction card、真实素材数量、已通过约束和权利状态：

```bash
python3 scripts/select_aesthetic_exploration.py \
  --category-code legal_utility \
  --primary-job search_answer \
  --carrier checklist_steps \
  --direction-card-id VDC11 \
  --materials verified_check_items,source_and_currentness,decision_or_action_order \
  --material-counts verified_check_items=3,source_and_currentness=1,decision_or_action_order=1 \
  --constraints no_generated_evidence,legal_review_complete,jurisdiction_and_date_visible \
  --rights-provenance-status passed \
  --prompt-id AP05 \
  --pretty
```

AP01 和 AP05 在法律清单、政策解释上可能共享 exact tuple，但承担的探索问题不同；因此命中多条时必须显式 `--prompt-id`，并用 `--rejected-prompt-ids` 保存淘汰方向。Selector 不会把多组 category/job/carrier 数组做笛卡尔积。

未知类目不会被静态资产假装“见过”。只命中 `analogue_cells_requires_review` 时返回 `analogue_review_required`；先保存 transfer rationale、补当前类目观察并形成新的本地 exact cell，静态 selector 不会因为传入一句“已审查”就自动放行。

## 返回状态

| 状态 | 含义 | 下一步 |
| --- | --- | --- |
| `matched_exploration` | exact scope、素材数量、约束、权利和禁用项通过 | 只做一个 `prototype_only` 粗原型 |
| `invalid_query` | 参数非法、prompt 不存在或 exact tuple 同时命中多条未选择 | 修查询并记录选中/淘汰理由 |
| `binding_controls_aesthetics` | 生产态或已有 exact binding | 禁用 overlay，只用 binding |
| `forbidden_output_state` | 请求 ready、viral、performance rule 或 traffic validated | 停止；本资产永远不能升级这些状态 |
| `no_exact_scope_cell` | 没有观察过的 exact tuple | 回到站内采样，最终为 `prototype_gap / brief_only` |
| `analogue_review_required` | 只命中迁移线索 | 先建立本地 exact cell，不自动选择 |
| `research_lead_only` | 如当前 AP02，站内 observation 本身不完整 | 补稳定 note、逐页 hash、权利与对照后再评审 |
| `incompatible_direction` | AP 与 VDC 不相容 | 不能让审美 overlay 替换证据骨架 |
| `needs_materials` | 任务和载体合适，但素材/禁用项失败 | 补真实素材或换载体，不让模型补证据 |
| `rights_or_provenance_blocked` | 授权、隐私、披露或来源未闭合 | 不生成 |
| `contraindication_blocked` | 命中任一禁用项 | 不生成 |
| `stale_or_tampered_evidence` | source/prompt hash 变化或复核过期 | 重新审计和发布资产 |
| `reset_required_after_two_rejections` | 同方向两次整体失败且没真正换输入 | 目标样本、prompt 模块、真实素材至少改两类 |

## 两个防过拟合检查

1. 去掉贴纸、字体和颜色后，页面任务是否仍成立？不成立说明仍在靠装饰冒充内容。
2. 同一个 prompt 换到另一个 primary job 是否仍“看起来能用”？如果能，它可能太泛；回到工作物、真实素材和反例重新收窄。

连续两次被评价为“像 PPT、像 AI、方向不对”时，停止微调。目标样本、主方向、真实素材三类至少改两类，再做下一版。
