# 风格经验从候选到生产调用

这条路径把真实帖子里的版式、素材、文案动作和表现差异，变成可查询、可绑定、可追溯的生产资产。它刻意区分三件事：看见一种风格、观察到公开互动代理相关性、证明平台流量因果。当前系统只支持前两层，绝不把公开点赞收藏写成“必爆公式”。

## 什么才允许晋级

一条可发布规则必须形成完整证据链：

```text
真实素材文件（实际 bytes）
  → style_assets（SHA-256、MIME、解码尺寸、使用状态）
  → visual/copy observation（具体风格特征）
  → feature_observation_links（精确绑定同次 post observation）
  → post_performance_publications（可重算表现层级）
  → rule_evidence（support / counterexample / boundary）
  → independent review receipt
  → qualified_style_publication
  → query / draft binding / binding review / publication
```

“同一个 post_id 上拼接不同时间的截图与指标”不算证据。每条 visual/copy evidence 都必须声明确切的 `post_observation_id`，并由 immutable feature link 同时签住素材、特征观察、采集 CSV 和表现计算。

晋级 `supported` 的最低门槛：

- exact `category × carrier × primary_job`，`applicability_scope` 必须逐字一致；
- 每条规则声明一个非空 `traffic_stage`，不能用 `null` 冒充全环节通用；
- copy rule 用 copy evidence 比较，visual/cover/rhythm/material rule 用 visual evidence 比较；
- matching-type support 中至少有两个独立账号、两个非重复内容簇，且都为 `high`；
- 至少一个 matching-type counterexample/boundary 为 `ordinary` 或 `low`；
- 公开代理证据必须是 `visibility_scope=public_proxy`、`traffic_verdict=not_applicable`；
- 同一帖子不能在一个规则包里既是 support 又是反例；
- 至少同时覆盖 copy 与 visual；独立 reviewer 与 content owner 不能是同一人。

这不是随意设高门槛：单账号可能只是账号权重，单内容簇可能只是选题红利，没有同类低表现样本也无法区分“风格机制”与“共同出现的装饰”。

## 最短闭环

```bash
python3 scripts/style_library.py create-archetype style.sqlite --record candidate.json
python3 scripts/style_library.py review-archetype style.sqlite --record archetype-review.json
python3 scripts/style_library.py publish-archetype style.sqlite --record archetype-review.json

python3 scripts/style_library.py query style.sqlite \
  --category 法律科普 --carrier checklist_steps \
  --primary-job search_answer --traffic-stage read_through \
  --materials text_only \
  --constraints deterministic_chinese_typesetting,no_generated_evidence

python3 scripts/style_library.py bind style.sqlite \
  --draft-id DRAFT-001 --draft-binding-id BIND-001 \
  --archetype-id ARCH-LAW-NATIVE \
  --category 法律科普 --carrier checklist_steps \
  --primary-job search_answer --business-objective engagement_proxy \
  --traffic-stage read_through --materials text_only \
  --constraints deterministic_chinese_typesetting,no_generated_evidence

python3 scripts/style_library.py review-binding style.sqlite --record binding-review.json
python3 scripts/style_library.py publish-binding style.sqlite --draft-binding-id BIND-001
```

`query` 只做 exact scope 与 exact traffic stage，不跨类目兜底。它返回实际选中的规则 payload、规则/证据哈希、support 与反例帖子、feature observation、表现层级和 per-rule evidence association；下游不是只拿一串规则 ID 猜风格。

规则必须声明 `selection_requirement`：

- `required`：素材、约束或依赖不满足时，整个 archetype 不可绑定；
- `optional`：可以排除该规则，但排除后仍须保留 copy + visual；
- `dependency_rule_ids`：依赖缺失时不能孤立使用，循环依赖在 candidate 阶段拒绝。

## candidate 关键合同

顶层字段为 `archetype_id/name/category/carrier/primary_job/audience_state/description/production_cost/confidence/archetype_version/rules`。规则示例：

```json
{
  "rule_id": "RULE-LAW-COPY",
  "rule_type": "copy",
  "applicability_scope": "法律科普×checklist_steps×search_answer",
  "payload": {
    "claim_kind": "contrastive_performance_hypothesis",
    "performance_evidence_scope": "public_proxy_association",
    "traffic_stage": "read_through",
    "required_material_codes": ["text_only"],
    "required_constraint_codes": ["no_generated_evidence"],
    "contraindication_codes": ["generated_person_as_evidence"],
    "prohibited_claims": ["guaranteed_viral", "traffic_causality"],
    "selection_requirement": "required",
    "dependency_rule_ids": [],
    "instruction": "短句先回答，再明确适用边界"
  },
  "evidence": [
    {
      "rule_evidence_id": "EVID-COPY-SUPPORT-A",
      "observation_type": "copy",
      "observation_id": "COPY-SUPPORT-A",
      "post_observation_id": "POST-OBS-SUPPORT-A",
      "evidence_role": "support",
      "limitations": "公开互动代理相关，不可复用原句"
    }
  ]
}
```

示例只展示一条 evidence；真实可发布规则仍必须满足两个独立高表现 support 与至少一个普通/低表现反例。

## 两次独立复核签了什么

Archetype review 仍使用 `selected_rule_ids/decision/target_status/content_owner_id/reviewer_ids/reviewed_at/limitations` 等字段，但 `selected_rule_ids` 必须等于该版本的完整 active rule set。收据写入 `archetype_review_receipts`，签住 candidate snapshot、规则包哈希和 feature/performance evidence 包哈希。复核后再改文案、规则或证据，旧收据无法发布。

发布是原子的：archetype snapshot、全部 rule publications 与 `qualified_style_publications` 同一事务落库。同一版本随后禁止新增、修改、删除规则或证据。当前 schema 的 `archetype_id` 本身不可变；修订规则包时要创建新的 archetype ID（例如 `ARCH-LAW-NATIVE-V2`）并递增 `archetype_version`，不能原地覆盖 v1。

Binding review 使用 `bind` 返回的 `pending_binding_sha256`。`draft_binding_review_receipts` 会再次核验：

- qualified publication 和 archetype review 仍存在；
- 被选规则及依赖仍匹配；
- 原素材当前仍 available，文件 bytes、MIME、完整解码和尺寸仍匹配；
- support/反例角色无交集；
- material plan 的 `performance_evidence_scope` 为标量；
- `primary_performance_rule_id` 属于 selected rules，且其 scope 与 aggregate scope 一致。

绑定复核收据和最终 publication 都不可修改。素材被撤回、文件被替换或证据过期后，即使曾经发布成功，后续 query/review/publish 也会 fail closed。

## 版本与边界

- 当前数据库 revision 是 `2.2-qualified-promotion`；旧 v2 不会静默迁移，必须显式重建/迁移后再用。
- 这条 CLI 从已经结构化的 SQLite observation 开始；浏览器发现结果仍需经过正式 capture/入库，脱敏 ledger 永远只是 candidate。
- `qualified_style_rules` 是“公开代理对照 + 多模态证据 + 独立复核”的风格规则数，不是第一方流量实验数。
- `first_party_traffic_validated` 仍不支持：当前 draft validator 尚未导入原始后台导出并程序重算结论，因此整个 scope 被 release gate 阻断；不可变 checkpoint 只能保存待审计观测，不能授予 win/loss 或“已验证流量”。
- 系统能防止伪证据、错范围、缺素材和复核后偷换，但不能保证爆款。它让下一轮生产与实验建立在可复用经验上，而不是把一次偶然高赞固化为玄学。
