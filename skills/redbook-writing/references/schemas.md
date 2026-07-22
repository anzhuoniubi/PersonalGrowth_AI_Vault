# 落库 Schema 与引用合同

本文件是运行目录的数据合同。字段名必须与 `scripts/validate_run.py` 一致；可以追加新字段，但不要改名、删必填字段或把多个概念塞进一个自由文本列。

该合同面向任意类目的跨类目生产。长期 style library 是“候选流量密码库”：保存可审计的模式、反例和表现 scope，不把成人、美妆、教育或任何单一类目当默认产品定位。

导航：[目录与 ID](#目录结构) · [Legacy](#legacy-v1-兼容边界) · [运行与证据账本](#runyaml) · [近期模板雷达](#trend-template-samplescsv-与-trend-template-candidatesjsonl) · [逐页风格](#style-samplescsv-与-style-recordsjsonl) · [账号帖子选题](#accountscsv) · [渠道与资格](#acquisition-channelscsv) · [成稿合同](#draftsmd) · [视觉资产](#视觉-brief原型与最终资产) · [引用图](#引用图)

## 目录结构

默认运行目录：`research/xiaohongshu/<YYYY-MM-DD>-<category>/`

```text
<run>/
├── run.yaml
├── research.md
├── query-log.csv
├── source-log.csv
├── claim-ledger.csv
├── accounts.csv                 # discovery / refresh
├── posts.csv                    # discovery / refresh
├── trend-template-samples.csv   # 近期模板雷达：逐帖结构与证据角色
├── trend-template-candidates.jsonl # 近期模板雷达：家族、生命周期与调用卡
├── topics.csv                   # discovery / refresh / draft
├── acquisition-channels.csv     # 涉及渠道时
├── sku-registry.csv             # 涉及商品时
├── offer-registry.csv           # 涉及非SKU内容/服务/订阅时
├── authorization-log.csv        # 涉及真人、投稿、聊天或案例材料时
├── production-gate-receipts.jsonl # 敏感/商业内容逐稿门禁
├── style-samples.csv            # discovery / refresh 逐页采集 manifest
├── style-records.jsonl          # discovery / refresh 可重放 journal
├── visual-briefs.jsonl          # 涉及视觉任务时
├── visual-prototypes.csv        # 双概念原型与 feed/full review
├── visual-feedback.jsonl        # 反馈与方向 reset
├── draft-assets.csv             # 最终逐页图片
└── drafts/
    └── <draft-id>.md             # draft
```

`mechanism` 需要前五个公共文件；`discovery/refresh` 另需账号、帖子、选题，并在 `style_requirement != none` 时需要逐页风格文件；近期模板雷达另需账号、帖子和两个 trend-template 文件；`draft` 另需选题和至少一篇成稿。即使复用历史证据，也把本次使用的来源/主张行复制或稳定引用到运行目录，使交付可独立审计。

长期私有库位于 `research/xiaohongshu/_style_library/`，保存 SQLite、第三方原图和安全派生物。整个目录必须被 Git 忽略；运行文件只引用 library ID、相对 locator 和 SHA-256，不复制图片 BLOB、第三方完整正文、账号凭据或隐私原件。

Skill 内的静态 assets 只提供 schema、空模板和候选方向，不保存第三方原图或版权受限正文。`assets/traffic-mechanisms-v1.json` 是带来源和边界的统一机制库；`assets/traffic-mechanism-candidates-template.jsonl` 用于新运行追加候选；`assets/visual-direction-cards-v1.json` 是 `candidate_only/not_performance_evidence` 的任务型视觉 brief 骨架，不能写入 published style rule 或 starter 字段。`assets/aesthetic-exploration-prompts-v1.json` 只在无 published binding 的显式探索中提供一次性审美 overlay，输出上限为 `prototype_only`；它不能进入最终 binding、starter 或 performance scope。

## ID 与多值规则

- 推荐前缀：`RUN-`、`Q-`、`OFF-/TECH-/ACA-/IND-`、`CLM-`、`ACC-`、`POST-`、`TTS-`、`TT-`、`TTF-`、`TOPIC-`、`DRAFT-`、`CH-`、`SKU-`、`OFFER-`、`AUTH-`。
- ID 在同一文件内唯一；`eligibility_id` 在 SKU 与 offer 两个 registry 之间也全局唯一。
- 多值字段使用分号 `;`，不要用中文顿号或自由文本混合 ID。
- URL 使用稳定的 `http(s)` 原始页面。账号按主页 ID/URL 去重；笔记按 note ID/URL 去重。
- 同一笔记被多个搜索命中时合并到一行，把路径写入 `queries_matched`。
- 近重复不直接删除；使用 `duplicate_of` 或 `cluster_id` 关联。

## Legacy v1 兼容边界

历史 run、`style-library-schema.sql` 与 `style-taxonomy-v1.json` 保持原字节和原语义。旧 primary job `recommendation_reach | search_capture | relationship_building | commercial_conversion` 只允许出现在 legacy v1 数据；读取时必须显式 `--allow-legacy-contract`，只能得到 legacy checkpoint，不能宣称当前 `VALID_COMPLETE`。

V2 使用 `run_contract_version: 2`、schema/taxonomy v2 和新文件合同。不得原地改写 v1、不得静默把旧 code 映射成新 code；升级走备份、canonical export、fresh v2 reingest、验证和人工确认。缺版本或未知版本 fail closed。

## run.yaml

顶层至少包含：

```yaml
run_id: RUN-20260716-001
run_contract_version: 2
mode: discovery
status: in_progress
created_at: 2026-07-16
category: "类目"
target_audience: "目标用户与具体处境"
primary_goal: "本次要回答的问题"
commercial_goal: "none | 具体商业目标"
traffic_funnel_stage: feed_stop
style_requirement: both
style_library_path: ../_style_library/style-library.sqlite
style_taxonomy_version: 2
trend_template_requirement: none
window_start: 2026-06-16
window_end: 2026-07-16
assumptions: []
limitations: []
```

允许模式：`mechanism | discovery | refresh | draft`。允许状态：`in_progress | complete | blocked`。V2 `style_requirement` 只允许 `none | copy | visual | both`；`trend_template_requirement` 只允许 `none | research | draft`：趋势发现/刷新写 research，使用模板生成稿写 draft，其他任务写 none。mechanism 通常为 none，discovery/refresh 的逐页风格研究通常为 both，draft 按交付物确定。`traffic_funnel_stage` 只允许 `feed_stop | read_through | save_share | comment_cocreation | profile_follow`，与 primary job 分开记录；后段行为不能冒充前段 exposure。只有公共数据集和该模式必需数据集均非空、成稿合同完整时才写 `complete`；权限或规则阻断写 `blocked`，未完成写 `in_progress`，不能用自定义近义词绕过完成门。`assumptions` 写模型采用的默认值，`limitations` 写登录、样本、日期、字段和后台不可见等真实缺口；二者不能省略。

验证器成功时分别输出 `VALID_IN_PROGRESS`、`VALID_BLOCKED` 或 `VALID_COMPLETE`；前两者只说明当前检查点内部一致，不能对外声称研究或成稿完成。

## query-log.csv

精确表头：

```text
query_id,platform,query,search_surface,sort_or_filter,run_at,result_count,selected_source_ids,selected_account_ids,selected_post_ids,new_valid_accounts,new_content_patterns,notes
```

- `search_surface`：web、notes、users、topics、comments、official_help 等。
- `sort_or_filter`：综合/热门/最新/图文/视频等，保留页面真实口径。
- `result_count` 不可见时留空，不估算。
- `new_valid_accounts` 与 `new_content_patterns` 用于停止条件；只有按统一定义判断后填写。
- 失败、登录墙、验证码、结果污染和个性化限制写入 `notes`，不要删除该查询。

## source-log.csv

```text
source_id,source_layer,platform,source_type,title,author_org,published_at,collected_at,url,query_id,access_status,evidence_form,evidence_grade,notes_file
```

- `source_layer`：official、engineering、academic、industry、creator_experience、rumor。
- `access_status`：full、partial、snippet_only、blocked、dead_link。
- `evidence_form`：official_page、pdf、paper、report、backend_screenshot、post、interview 等。
- `evidence_grade`：A/B/C/D；等级衡量证据，不衡量结论是否喜欢。
- `published_at` 接受 `YYYY`、`YYYY-MM` 或 `YYYY-MM-DD`，不明可空；不要补造日级精度。`collected_at` 必须为 `YYYY-MM-DD`。
- 页面失效或被弃用也保留，更新状态与笔记，避免以后重复踩坑。

## claim-ledger.csv

```text
claim_id,category,claim_text,source_ids,counter_source_ids,evidence_grade,claim_status,scope,confidence_reason,skill_action,last_verified_at,verification_class
```

- `claim_text` 写一个可判断真假的规范化主张，不写长段总结。
- `source_ids` 与 `counter_source_ids` 必须指向 source log。
- `claim_status`：`confirmed | supported_experience | hypothesis | contradicted | unknown`。
- `verification_class` 是强制枚举，不从自由文本 `category` 猜：`current_runtime | historical_research | mechanism_evidence | experience | hypothesis`。涉及当前平台规则、法律、资格、产品能力或政策变化时必须选 `current_runtime`；“本轮未确认某当前能力”的负向边界也属于 current_runtime/unknown。它强制本次运行日的可访问官方来源，不能借自由 category、否定前缀或 `experience` 规避。
- `scope` 精确到时间、产品模块、入口、内容/商业面；禁止只写“全平台”。
- 主张的 `evidence_grade` 不得高于其最佳支持来源；多条弱来源不会自动合成为 A 级。
- C/D 级来源不得把主张标为 `confirmed`；D 级不得升为 `supported_experience`。
- `skill_action` 写“允许怎样说/必须怎样测试/必须阻断”，不写流量承诺。
- `current_runtime` 主张每次运行复核 `last_verified_at`，且支持来源本次重新采集；历史论文不能单独确认当前规则。

## accounts.csv

```text
account_id,account_name,profile_url,head_type,follower_count,window_start,window_end,recent_sample_n,recent_median_visible_engagement,recent_max_visible_engagement,outlier_multiple,audience_evidence,commercial_distance,collected_at,source_ids,confidence,status
```

- `head_type`：scale、recent_performance、audience_precision、commercial_adjacent，可多值。
- `follower_count` 和公开互动不可见时留空；不要补零。但字段不可见时不能把该账号标为 `scale`。
- `recent_sample_n` 只计算窗口内连续可判日期样本。
- `outlier_multiple = recent_max / recent_median`；中位数为 0 或字段不可比时留空。
- `audience_evidence` 写简介、反复议题、评论问题等公开证据，不根据头像/姓名推断身份。
- `source_ids` 必须回指 source log；主页 URL 本身不能替代查询与采集证据。
- `commercial_distance`：far、adjacent、near、direct；与内容质量分开。
- `status`：candidate、focus、excluded、stale，并在研究文档解释排除原因。
- `focus` 或 `high` confidence 不能使用 0 条近期样本。`candidate/focus + recent_performance` 必须同时有正数 `recent_sample_n`、有限非负数 median/max/outlier，且 max 不得小于 median；指标不可比或中位数为 0 时移除 `recent_performance`，不要用空字段、NaN 或 Inf 完成“表现头部”调研。`outlier_multiple` 必须等于可比公开指标的 max/median。

## posts.csv

```text
post_id,note_id,title,url,account_id,published_at,date_confidence,collected_at,queries_matched,search_surface,sort_or_filter,rank_observed,format,visible_engagement,engagement_breakdown_available,account_baseline_multiple,hook,page_or_scene_structure,need_signal,cover_mechanism,evidence_level,confidence,duplicate_of,cluster_id,status,performance_tier,style_capture_status,style_library_post_id,style_observation_ids,style_skip_reason
```

- `date_confidence`：high、medium、low、unknown。含混相对日期不得纳入严格 7/30 天结论。
- `rank_observed` 只是当时当前环境的位置，不叫平台排名。
- `visible_engagement` 原样保存页面显示；合并数不拆分。
- `account_baseline_multiple` 只在同账号、同一公开指标可比时计算。
- `active` 选题引用的 observed/calculated 帖子必须同时有可见互动记录和数值型 `account_baseline_multiple`；没有表现指标的需求材料只能支撑 `experimental`，不能冒充高表现证据。
- `page_or_scene_structure` 逐页/逐场景记录任务，不只抄正文摘要。
- `need_signal` 区分求方法、分享经历、反对质疑、询问商品、泛泛夸赞。
- `evidence_level`：observed、calculated、inferred、hypothesis。
- `status`：active、excluded、stale；排除不等于删除。
- `performance_tier`：`high | ordinary | low | unknown`，必须来自本轮同账号可比 baseline，不凭印象填写。
- `style_capture_status`：`complete | partial | skipped | not_required`。`complete` 必须填写真实 `style_library_post_id` 与同帖 copy/visual observation IDs；其他状态必须写 `style_skip_reason`。
- 完成态 discovery/refresh 中，每个 active high/low 或被 topic 引用的 post 都必须 `complete`。验证器会打开 `run.yaml.style_library_path` 指向的 v2 SQLite，核对 note/url/category、`run_post_refs`、精确 `posts.csv` SHA、performance tier，以及同一 post 中符合 `style_requirement=copy | visual | both` 的 observation；仅在 CSV 手填 ID 不能通过。

## trend-template-samples.csv 与 trend-template-candidates.jsonl

用户要求近期爆火模板、拍摄灵感、挑战/转场/跟拍或模板生命周期时，除通用 query/source/post 账本外，必须创建这两个文件。完整流程见 [trend-template-radar.md](trend-template-radar.md)。

`trend-template-samples.csv` 每个已打开并编码的帖子一行，精确表头：

```text
template_sample_id,template_id,family_id,post_id,note_id,url,account_id,query_ids,parent_query_id,query_round,search_surface,sort_or_filter,rank_observed,published_at,date_confidence,collected_at,carrier,primary_job,template_type,remix_relation,creative_family_id,lineage_cluster_id,supply_origin,hook_observation,shot_grammar_observation,edit_grammar_observation,participation_signal,visible_engagement,account_baseline_multiple,performance_tier,evidence_role,duplicate_of,category_scope,comment_evidence_ids,source_ids,access_status,source_snapshot_sha256,capture_status,limitations
```

- `evidence_role`：`seed | support | counterexample | boundary`。同一行只能承担一个主要角色；同一 post/source 不能同时支持并冒充反例。
- `template_type` 使用 radar 中的受控类型，可用分号组合；`carrier`、`primary_job` 与 `category_scope` 独立保存。
- `remix_relation`：`direct_remake | slot_substitution | category_transfer | parody | tutorial | generator | unrelated_same_phrase`。`creative_family_id + lineage_cluster_id + account_id` 用于搬运/同源去重，不以账号数直接冒充独立复刻。
- `supply_origin`：`spontaneous | brand_campaign | platform_program | paid_distribution | mixed | unknown`；没有来源证据时必须 unknown。
- `parent_query_id/query_round` 保存本样本的追链位置；完整查询仍写 `query-log.csv`。`source_snapshot_sha256` 只有真实保存了合规页面快照/证据文件时才填 64 位哈希，否则留空并降低 access/capture 状态。
- `hook/shot/edit` 保存结构观察，不复制第三方完整脚本；无某段语法时写 `not_applicable`，不可留空后假装已采集。
- `participation_signal` 写求模板、交作业、视频/图片回复、站队或复刻的匿名语义和 comment evidence IDs；没有则写 `none_observed`。
- `performance_tier/account_baseline_multiple` 仍按 `posts.csv` 的同账号可比基线合同；不可比时为 `unknown/空`，不因模板名热门而填 high。
- `capture_status`：`complete | partial | blocked | excluded`。只有原帖结构、日期、来源与所需评论角色都可核验时为 complete。

`trend-template-candidates.jsonl` 每行是一张可版本化模板卡，字段合同：

```text
record_type,schema_version,candidate_record_id,run_id,candidate_version,supersedes_candidate_record_id,template_id,family_id,canonical_name,aliases,template_types,discovery_queries,discovery_lanes,source_sample_ids,support_sample_ids,counterexample_sample_ids,boundary_sample_ids,independent_account_count,category_scopes,carrier_scopes,primary_job_scopes,traffic_stage_scopes,supply_origin,supply_origin_evidence_ids,first_seen_at,last_seen_at,sample_window,window_comparisons,hook_grammar,shot_grammar,edit_grammar,participation_loop,slot_map,required_material_codes,optional_material_codes,contraindications,rights_status,safety_status,authorized_asset_ids,source_asset_hashes,replication_status,lifecycle_phase,lifecycle_reason,confidence,evidence_level,performance_evidence_scope,decision,adaptation_notes,last_refreshed_at,limitations,record_sha256
```

- `record_type=trend_template_candidate`；`schema_version=1`。每行有稳定 `candidate_record_id` 与 canonical `record_sha256`。同一 `template_id` 的刷新递增正整数 `candidate_version`，并用 `supersedes_candidate_record_id` 指向长期库上一版。长期库不修改旧行；运行文件每个 template 恰好一张 current snapshot，并须是哈希有效的最高版本。
- `replication_status`：`query_candidate | observed | replicated`；`lifecycle_phase`：`unknown | rising | mature | fatigued | evergreen_carrier`。前者回答结构是否独立复刻，后者回答时序；不得揉成一个状态。
- 所有非 `unknown` 生命周期必须有至少两个可比 `window_comparisons`。每项精确保存 `start/end/support_sample_ids[]/independent_derivatives`；窗口不重叠，每条 support 恰好出现一次，发布日期必须落在对应窗口，独立数由 account、lineage 与去重 post identity 重算。空对象、手填计数和单一横截面不能写 rising/mature；评论参与是可选加强证据，不是所有模板必需。
- `decision`：`shoot | adapt | observe | skip`，分别对应拍、改后拍、观察、不追。占位模板必须是 `query_candidate + observe`。
- `shoot/adapt` 必须同时满足：current、replicated、合法 lifecycle、独立反例、exact category/carrier/job/stage、`rights_status=grammar_only|authorized_assets`、`safety_status=passed` 和真实素材映射；`query_candidate/observed/fatigued/unknown` 硬阻断。
- `source/support/counterexample_sample_ids` 只能引用同次或稳定引用的 sample 行；sample 的 `post_id/note_id/canonical URL/account_id/published_at` 必须与 `posts.csv` 精确闭合，同一 post identity 不能跨角色复用。搬运、同账号和同源素材去重后再计 `independent_account_count`。
- `boundary_sample_ids` 保存相似表面但不同任务/语法的边界；`discovery_lanes` 至少标 `named_trend | unnamed_structure_cluster` 之一，避免只找到已命名、已成熟的 SEO 模板。
- `slot_map` 必须结构化保存 `fixed[] / replaceable[] / new_semantic_contribution`；`carrier_scopes/primary_job_scopes/traffic_stage_scopes` 用于生成 exact 检索。
- `performance_evidence_scope` 当前只允许 `not_performance_evidence | public_proxy_association`；主 Skill 的一方 verdict 重算仍禁用，不能在模板卡手填 `first_party_traffic_validated`。
- `required_material_codes` 必须在生成时映射为本 run 可解析的 Source / Claim / Post / Authorization / authorized material ID 数组；空字符串、不存在 ID 或不兼容证据类型都不能通过。
- `rights_status`：`grammar_only | authorized_assets | needs_review | blocked | unknown`；`safety_status`：`passed | needs_review | blocked | unknown`。只有使用源资产时才可写 authorized_assets：`authorized_asset_ids` 精确填写当前 `authorization-log.csv.material_id`，`source_asset_hashes` 精确匹配相应 `material_sha256`，授权必须 current、允许 adaptation/verbatim 且 commercial use approved。只复用抽象语法写 grammar_only。
- 模板卡只保存可迁移语法。原作者标题、人物、独特台词、视频、图片、BGM 和受版权限制素材不得作为 reusable asset 入库。

## style-samples.csv 与 style-records.jsonl

`style-samples.csv` 是逐页完成清单，精确表头：

```text
style_sample_id,post_id,query_ids,performance_tier,carrier,primary_job_scope,slide_count_visible,visible_slide_indexes,slide_count_captured,captured_slide_indexes,visual_observation_ids,copy_observation_ids,archetype_ids,evidence_role,capture_status,limitations
```

- `visible_slide_indexes` 与 `captured_slide_indexes` 都是按真实页序记录的 exact set；`complete` 要求二者相等、无重复/缺页，并能解析每页所需 observation。
- `capture_status`：`complete | partial | blocked | excluded`；`evidence_role`：`support | counterexample | boundary | unassigned`。Partial/blocked 必须保留原因和续跑点，但不能升级规则或放行 ready draft。
- query 选中的高表现图文/轮播及同账号普通/低表现对照各有且只有一行；不同 primary job 或载体的样本只能作 boundary，不能伪装 matched control。

`style-records.jsonl` 每行是一个可重放 JSON object，至少包含 `record_type`、稳定 record ID、`run_id`、`taxonomy_version` 和 canonical payload/hash。允许对象包括 identity mapping、asset reference、post metric、slide、visual observation、copy observation、rule/evidence/binding publication；不保存图片 BLOB、第三方长文或凭据。导入时 journal、manifest、posts、accounts 和 query log 必须在同一事务对账，任一断链全部回滚。

### 风格规则的主张边界

`claim_kind` 只允许：`series_constant | task_fit | contrastive_performance_hypothesis`。`performance_evidence_scope` 只允许：`not_performance_evidence | public_proxy_association | first_party_traffic_validated`。

- `series_constant` 与 `task_fit` 必须为 `not_performance_evidence`。
- 公开互动经过闭合 matched-control feature contrast 后，最多是 `public_proxy_association`；`public_proxy ≠ traffic`。
- `first_party_traffic_validated` 必须来自使用该 rule 的 published binding、自有账号 first-party impressions/reach、预注册 checkpoint、逐指标 canonical hash、metric-set hash 和不可变 outcome receipt。观察窗口由预注册实验决定，不把 24h/72h 写成跨类目默认。点赞、收藏、评论、搜索位置、CTR 或停留不能替代 exposure primary。当前验证器尚不能导入原始后台导出并程序重算结论，因此整个作用域保持禁用；checkpoint 只能作为待审计观测，不能让任何 draft 获得“已验证流量”、`win` 或 `loss`。
- Query、archetype、binding、draft frontmatter 和报告必须原样外显 scope，不能在输出层升级措辞。

当前真实 qualified-cell 门禁若记录 `qualified_cells=0`，starter pack 必须不存在或保持禁用，任何 `starter_applied` 都是无效绑定。无合格 library/starter 时唯一合法绑定状态是 `needs_style_research`，不得生成或宣称 ready 稿。只有严格绑定三槽 task-fit 机制、独立反例/anti-pattern，并通过事实、授权、真实性和商业门，才可生成显著标注的 `candidate_only / needs_review` 文案、结构 brief；有合法素材时图像最多为 `prototype_only`。否则只输出补采计划。

### 一方发布与 outcome 顺序

一方学习链固定为：

```text
draft_experiments + assignments（actual_publish_at 必须为空）
→ draft_experiment_publications（冻结预注册与 assignment set）
→ draft_publish_events（真实发布后新增一次，不回写预注册行）
→ draft_outcome_checkpoints + metrics
→ draft_outcome_publications（冻结 metric set）
```

`draft_publish_events` 锁定 exact experiment/binding/account/surface/post ID/URL/actual time 和 canonical hash，且只能在 experiment publication 之后追加；更新或删除被阻断。Checkpoint 的 `observed_at` 必须接近 `actual_publish_at + checkpoint_hours`，容差为 `min(2h, checkpoint_hours × 10%)`；`checkpoint_hours` 是预注册正整数，不是固定平台规律。这样短窗口不能在发布同一秒伪装成已观察，长窗口也不能无限回填。

Publication insert 还会重算 assignment row hash、ordered assignment-set hash/count、held constants、planned order 与完整 preregistration preimage；publication/event/checkpoint 的记录时间只能接近数据库当前时间。当前没有 pair-contrast publication 表，所以 `blocked_2x2` 在 schema 中 fail closed，只允许保存设计，不允许发布成已预注册实验。

## topics.csv

```text
topic_id,topic,primary_job,entry_surface,target_audience,specific_scenario,core_promise_or_tension,evidence_ids,counterexamples,lifecycle,format,format_reason,commercial_distance,rule_scopes,measurement_plan,hypothesis_id,priority,status,last_seen_at
```

- V2 `primary_job`：`feed_stop | search_answer | explain | trust_build | decision_support | relationship_build | conversion | authority_statement`。Legacy v1 四值只按上节兼容读取，不进入 v2 新行。
- `evidence_ids` 可以引用 source、claim、account、post；必须至少指向实际样本。
- `experimental` 至少引用一个可访问的需求/访谈/评论/内容样本；官方规则或机制来源本身不能生成选题。`active` 至少引用两个不同、可追溯账号在本次窗口内的 active observed/calculated 帖子；不足则保持 `experimental`。
- `counterexamples` 写独立反例 ID 与其否定的范围，不写“暂无”；同一 ID 不能同时出现在 `evidence_ids` 和反例中。
- `lifecycle`：hot、periodic、evergreen_search。
- `measurement_plan` 至少包括主指标、可用代理、观察窗口、失败层级、下一次单变量。
- `status`：experimental、active、deprecated；旧选题降级，不静默删除。

## acquisition-channels.csv

```text
channel_id,direction,platform,account_scope,audience_state,channel_role,native_format,source_asset_id,public_identity,eligibility_ids,surfaces,permitted_cta,prohibited_cta,landing_asset,primary_metric,metric_availability,data_source,event_definition,diagnostic_metrics,attribution_method,attribution_level,baseline_window,test_window,minimum_events,decision_rule,compliance_scope,evidence_ids,confidence,owner,status,source_asset_sha256,consent_ids
```

- `direction` 只能是 external_to_xhs、xhs_to_native_conversion、xhs_to_approved_external、owned_retention。
- 每行只表示一个原生 `platform` 与一个真实账户/主体 `account_scope`；`unassigned` 只能用于阻断态，不能放行 CTA。
- 每个渠道只有一个主要 `channel_role` 和一个 `primary_metric`。
- `eligibility_ids` 引用下面两个 registry；商业 CTA 不得留空。
- `surfaces` 必须与被引用 registry 行逐项一致。
- `metric_availability` 真实写 available/unavailable/needs_backend_check。
- `event_definition` 写去重、同意、退款等边界；不能只写“转化”。
- 无用户级闭环的 external_to_xhs 使用 `attribution_level=directional`。
- `source_asset_sha256` 锁定本行实际素材版本；`user_level_with_consent` 还必须用 `consent_ids` 引用当前有效、明确允许跨平台归因且绑定该素材的 AUTH 记录。
- 资格未全部通过时，`status` 必须以 blocked/draft/needs_ 开头。

## sku-registry.csv

```text
eligibility_id,sku_id,sku_name,platform,account_scope,surface,source_asset_id,status,evidence_ids,platform_ticket,verified_at,expires_at,material_limits,qualification_requirements,notes,source_asset_sha256,qualification_claim_id
```

一个 SKU 每个 `platform × account_scope × surface × source_asset_id` 各一行。`source_asset_id` 是本次审批覆盖的具体稿件/素材；成稿时等于 `draft_id`，渠道时等于该行的 `source_asset_id`。常见 surface：organic_content、professional_account、shop、pgy_commercial_content、ads、leadgen、dm_commercial、approved_external_destination。

允许放行状态只有 `confirmed | approved`，且 `platform`、`account_scope`、`surface`、`source_asset_id` 都必须指向一个具体对象，不能写 `multi_platform`、`all_*` 或 `unassigned`。`source_asset_sha256` 锁定获批素材的精确字节版本。`platform_ticket` 必须引用 `source-log.csv` 中本次采集、可访问的官方审批记录；`qualification_claim_id` 必须引用与完整元组和素材哈希一致的当前 `sku_eligibility` 主张，两者同时出现在 `evidence_ids`，不可只引用一般规则自填 `confirmed`。必须有不晚于本次运行的 `verified_at`；若无 `expires_at` 就在本次运行重新核验，有明确有效期时本次运行日不得晚于它。其余状态使用 needs_platform_confirmation、insufficient_sku_input、insufficient_official_evidence、expired、rejected、blocked 等。一个账户、素材或 surface 通过不能放行另一个。

最小 SKU 资格主张作用域示例（键名必须保持一致）：

```text
sku_id=SKU-001|platform=xiaohongshu|account_scope=acct-xhs-001|surface=shop|source_asset_id=DRAFT-001|source_asset_sha256=<64位SHA-256>
```

## offer-registry.csv

```text
eligibility_id,offer_id,offer_name,offer_type,platform,account_scope,surface,source_asset_id,status,evidence_ids,platform_ticket,verified_at,expires_at,permission_or_consent_requirements,prohibited_uses,notes,source_asset_sha256,qualification_claim_id
```

非 SKU 的编辑内容、订阅、咨询、合作、活动、投稿计划使用 offer registry。不能用 `multi_platform/public_content` 一行放行所有平台；按具体 `platform × account_scope × surface × source_asset_id × source_asset_sha256` 拆分，并用 `platform_ticket + offer_eligibility qualification_claim_id` 保留精确审批记录。若内容同时植入商品，还必须追加 SKU eligibility。

最小 offer 资格主张作用域示例：

```text
offer_id=OFFER-001|offer_type=subscription|platform=xiaohongshu|account_scope=acct-xhs-001|surface=shop|source_asset_id=DRAFT-001|source_asset_sha256=<64位SHA-256>
```

## authorization-log.csv

```text
authorization_id,subject_scope,source_asset_id,material_id,material_sha256,material_type,permission_scope,commercial_use,anonymization_requirements,granted_at,expires_at,withdrawal_process,evidence_locator,verified_by,verified_at,status,authorized_output_sha256
```

- 涉及真人投稿、访谈、聊天记录、案例、匿名改编或合成案例时使用；不要把身份证、联系方式、原始聊天等隐私原件直接放进研究库。
- `material_type`：`first_party | interview | submission | case_record | chat_record | other`。
- `source_asset_id` 指向获授权用途的具体稿件/渠道素材；`material_id + material_sha256` 锁定被授权原材料，`authorized_output_sha256` 锁定当事人/核验人实际审过的衍生稿或归因素材。任一字节变化都要重新审查并更新授权，禁止拿一份无关授权套另一案例。
- `permission_scope` 可用分号组合：`anonymized_publish | adaptation | composite | verbatim | cross_platform_attribution`。用途不能从“同意采访”自动扩张到公开、改编、跨平台用户级归因或商业使用。
- `first_person_documented` 必须在可见披露中明确“本人/我的亲历”；涉及他人材料时，每条 AUTH 还必须包含 `anonymized_publish` 或 `verbatim`，仅有归因同意不能发布内容。`composite_cases` 至少需要两个不同 `subject_scope`、`material_id` 和 `material_sha256`；换 ID 复制同一材料不算两个案例。
- `commercial_use`：`approved | prohibited`；有商业关系的案例稿必须获得对应商业用途许可。
- `evidence_locator` 只写受控原件的保管编号/私有库定位符；`verified_by` 与 `verified_at` 记录谁在何时核验。不要伪造授权编号。
- `status`：`approved | pending | withdrawn | expired`。无 `expires_at` 的 approved 记录需在本次运行复核；撤回后立即阻断关联稿件。

## production-gate-receipts.jsonl

成人亲密关系、性健康或成人用品内容同时涉及商品、品牌关系、佣金、获赠、付费分发、商业 CTA 或站外 destination 时，每稿必须追加一条 `adult_sensitive_commercial_gate` receipt。至少锁定 `receipt_id`、`draft_id + draft_sha256`、exact SKU/offer、library account、delivery surface、asset version、authorization/rights/consent、精确 `commercial_relationship + disclosure_text`、`audience_age_floor >= 18`、非空 `minor_access_controls`、series/product/UGC lineage、distribution/destination/attribution、人工 reviewer、与本次 run 同日的 reviewed_at、gate status、limitations 与 canonical receipt SHA-256。`receipt_sha256` 使用对“移除 receipt_sha256 后的完整 object”做 UTF-8、key sort、compact JSON 的 SHA-256；改变任何字段都要重新审查并重签。

只有所有必填字段可核验且 `gate_status=pass` 才能进入商业 CTA 审查；missing/unknown/expired/blocked 一律使 draft blocked。Receipt 只是当前稿件与 surface 的生产门禁，不是平台批准、流量证据、风格证据或对其他 SKU/账号/素材的通行证。模板 `assets/production-gate-receipts-template.jsonl` 默认 blocked，不能复制其占位值冒充 pass。

## drafts/*.md

Frontmatter 必填：

```yaml
---
draft_id: DRAFT-001
topic_id: TOPIC-001
platform: xiaohongshu
account_scope: none
primary_job: search_answer
lifecycle: evergreen_search
truth_label: factual_explainer
truth_disclosure_text: 事实说明
truth_disclosure_location: 首屏
authorization_ids: none
source_material_ids: none
commercial_relationship: none
disclosure_text: none
disclosure_location: none
answer_location: "第3页/正文第2段"
cta_type: none
eligibility_ids: ""
surfaces: ""
status: needs_review
---
```

V2 成稿还必须写 `style_contract_version: 2`、`style_requirement`、`style_library_path`、`style_taxonomy_version`、category/carrier/job/material/constraint query scope、published binding 的完整回执字段、`performance_rule_claim_kind`、保守的 `performance_evidence_scope`、`primary_performance_rule_id`、`style_binding_status` 与 visual delivery。`grounded` 必填 `draft_binding_id / draft_binding_sha256 / style_rule_ids / primary_style_archetype_id / primary_style_archetype_version / primary_style_archetype_snapshot_sha256`，并与本地 SQLite 中 immutable publication 完全一致；有 performance scope 时 `primary_performance_rule_id` 必须是 selected rules 中唯一明确的主表现规则，且 binding material plan 中的 primary scope 必须与 frontmatter 一致。`needs_style_research` 或 `not_performance_evidence` 时 primary rule 为 `none`，不得自由文本声明。曝光主指标与任务主指标必须分开：`traffic_primary_metric` 只描述 impressions/reach 或明确不可得；`job_primary_metric` 按 primary job 选择，并同时写 `job_metric_event_definition`、`job_metric_denominator`、`job_metric_data_scope` 与 `job_metric_verdict`。一方观测还必须写 `traffic_observation_surface / traffic_outcome_checkpoint_id / traffic_outcome_receipt_sha256`，并与同一个 SQLite checkpoint 完全一致；非一方作用域三项必须为 `none`。公开评论只能使用 `comment_semantic_proxy/comments/not_applicable`，不能包装成任务胜负。`style_binding_status=needs_style_research` 时 draft 顶层只能 needs_review/blocked；候选路径还必须通过下方流量机制合同，且视觉状态不得高于 `prototype_only`。`starter_applied` 在 qualified-cell 门禁发布前不可用。

`truth_label` 只允许：`first_person_documented | authorized_anonymized | authorized_adaptation | composite_cases | fictional_scenario | factual_explainer`。`truth_disclosure_text` 必须使用肯定式合同（如“本内容为明确虚构”“经授权匿名整理”“本人亲历记录”），并在 `truth_disclosure_location=首屏/第一页/首段/开头/标题下` 的实际可见正文里出现；“不是真实虚构”“未经授权”等否定冲突会阻断。HTML 注释、隐藏标签、图片 alt、链接 URL 或只存在元数据中的文字不算可见。`authorization_ids` 必须与标签一致：本人一手材料写 `self_only`；授权匿名/改编引用相应 AUTH；合成案例至少引用两个允许 composite 且对应不同 subject/material/hash 的 AUTH；明确虚构与纯事实解释写 `none`。`source_material_ids` 必须与关联 AUTH 的 `material_id` 完全一致。商业关系是独立维度，`commercial_relationship` 只允许：`none | owned_product | sponsored | gifted | affiliate | commissioned_creator | other_disclosed`；非 `none` 时披露文案必须真实、肯定地写入 `## 成稿`，并与关系类型对应：自有/自营、广告/品牌合作、获赠、佣金/返佣、受委托，或明确的其他利益关系。“不是广告/没有品牌合作”等否认句会阻断。机器可验证位置仅支持首屏/第一页/首段/开头/标题下，或 `CTA前/正文CTA前`；后两者要求同一成稿中披露确实早于精确 `cta_copy`。视频口播与字幕等无法由 Markdown 单独证明的位置先由人工审校，不得伪填成机器 PASS。

`cta_type` 只允许：`none | save | follow | comment_question | read_series | product_component | leadgen | approved_external | paid_offer`。后四种商业 CTA 不能把商业关系写成 `none`，并必须引用当前有效且与 `platform × account_scope × surface × draft_id/source_asset_id` 完全一致的 eligibility。

正文二级标题必须完整且名称固定：

```text
## 证据与目标用户
## 标题版本
## 封面版本
## 流量机制绑定
## 趋势模板绑定
## 视觉方向绑定
## 成稿
## 关键词与话题
## 事实与证明
## CTA 与披露
## 合规审校
## 创意审校
## 观测计划
```

`## 流量机制绑定` 固定包含以下机器字段：

```text
contract_status: needs_research | bound_candidate | bound_grounded
primary_mechanism_id: TMxx | none
mechanism_ids: TMxx;TMxx;TMxx | none
counterexample_ids: 本次运行中的真实 Source/Claim/Account/Post ID | none
material_codes: 统一机制库中的素材代码 | none
material_evidence_map: 单行 JSON object | none
mechanism_application_map: 单行 JSON object | none
research_gap: 精确缺口
```

绑定态必须恰好一条 content、一条 carrier_router/truth_gate、一条 feedback/measurement/governance；ID、job、stage、carrier、requires/conflicts、required/forbidden materials 全部按 `traffic-mechanisms-v1.json` 校验。`material_evidence_map` 不能引用不存在的材料，反例 ID 不能同时充当支持材料。`mechanism_application_map` 的 keys 必须与三张卡完全一致，并逐卡写 `input_refs / title_action / cover_action / body_action / comments_action / job_metric / failure_condition / intentional_deviation`。

`## 趋势模板绑定` 固定包含：

```text
template_contract_status,candidate_record_id,template_id,family_id,candidate_version,replication_status,lifecycle_phase,last_refreshed_at,decision,source_sample_ids,support_sample_ids,counterexample_sample_ids,fixed_slots,replaced_slots,new_semantic_contribution,material_evidence_map,failure_condition
```

所有 v2 draft 都必须保留本节。不使用模板时 `template_contract_status=not_used` 且其余字段为 none。使用时必须为 `bound_candidate`，`run.yaml.trend_template_requirement=draft`，并与同一 template 的哈希有效最高版本在 record/template/family/version/status/phase/decision/sample IDs 上完全一致；模板卡还须在本次窗口刷新、replicated、合法时序、shoot/adapt、权利/安全通过。素材 JSON 必须覆盖候选卡全部 required material codes，每个 code 对应非空本地证据/素材 ID 数组；未知 ID 或未闭合授权不能通过。该 section 只放行模板语法引用，不替代流量机制、style binding、授权、商业与最终视觉门。

`## 视觉方向绑定` 固定包含 `visual_contract_status / visual_direction_card_ids / selection_mode / asset_manifest_path / asset_manifest_sha256 / style_library_path / draft_binding_id / active_contraindication_codes / research_gap`。选择器必须按 exact `primary_job × carrier × manifest materials × contraindications` 重算；探索态最多 `prototype_only`，production 必须同时命中同一 `style_library_path` 中的 published `draft_binding_id`，卡片本身不得决定 palette、typography、image treatment、density、annotation 或 crop。

商业 CTA 的 `eligibility_ids` 与 `surfaces` 必须对应且全部 approved/confirmed。`cta_type=none` 才可留空。验证器检查结构和引用，不会替代语义、创意、版权、医学或平台人工审核。

`## CTA 与披露` 中必须逐行写 `cta_type`、`cta_copy`、`commercial_relationship`、`disclosure_text`、`disclosure_location`、`eligibility_ids`、`platform`、`account_scope`、`surfaces`，并与 frontmatter 完全一致。验证器能发现两处自相矛盾，但仍需审校者通读成稿，确认正文或画面没有在 `cta_type=none` 时暗藏购买/站外动作。

成稿 `status` 只允许 `needs_review | ready | blocked`。`run.status=complete` 时，每篇成稿必须为 `ready`，且 `## 合规审校` 与 `## 创意审校` 都包含 `review_status: PASS`；PARTIAL/FAIL 不得靠把运行标完成来绕过。

## 视觉 Brief、原型与最终资产

`visual-briefs.jsonl` 每行一个不可变 revision，字段合同：

```text
visual_brief_id,draft_id,brief_revision,visual_brief_sha256,binding_snapshot_sha256,primary_job,carrier,audience_state,attention_paths,functional_need,lived_scene,motive_codes,perceivable_outcome,brand_to_user_translation_trace,offer_or_sku_ref,distribution_mode,content_owner_id,reviewer_ids,reviewer_independence_status,content_model_id,content_model_version,model_lifecycle_stage,page_role_plan,required_material_codes,forbidden_feature_codes,brand_prominence,prototype_count,feed_preview_size,full_size,constraint_codes,benchmark_library_post_ids,target_hypothesis_sha256,benchmark_set_sha256,attention_path_set_sha256,generation_prompt_sha256,supersedes_visual_brief_id,reset_of_visual_brief_id,created_at
```

只有选择器找到至少两个各自有证据依据、去重 attention path 时才设置 `prototype_count >= 2`；exact cell 只有一个合格探索方向时最多生成一个 `prototype_only`，不得为凑数临时造方向或声称完成比较；没有合格方向时记录 `prototype_gap` 并停在 `brief_only`。Starter/candidate 只能 `model_lifecycle_stage=explore`；ready 需要独立 reviewer。Brief 不保存选中结果或用户反馈。

`visual-prototypes.csv` 精确表头：

```text
prototype_asset_id,draft_id,visual_brief_id,concept_id,attention_path,prototype_prompt_sha256,asset_path,asset_sha256,width,height,render_method,binding_rule_bundle_sha256,style_rule_refs,starter_prompt_id,starter_prompt_sha256,feed_preview_path,feed_preview_sha256,feed_review_status,full_review_status,selection_status,selection_reason,revision_of,notes
```

每个原型必须是实际文件，完成 `feed_preview` 与 `full_size` 查看。Library 资产的 rule refs 是 published binding 的非空子集；starter 资产不得写 rule refs。只改色/字体不构成第二概念。

`visual-feedback.jsonl` 每行一个按序事件：

```text
feedback_event_id,draft_id,visual_brief_id,prototype_asset_id,event_index,feedback_scope,reason_codes,feedback_text_sha256,recorded_at,caused_reset,new_visual_brief_id
```

连续两次 holistic rejection 后，第三次渲染前必须生成新 brief 并保存 reset proof；不能只修改布尔值。

`draft-assets.csv` 精确表头：

```text
draft_asset_id,draft_id,draft_binding_id,slide_index,asset_path,asset_sha256,width,height,render_method,binding_rule_bundle_sha256,style_rule_refs,starter_prompt_sha256,review_status,review_receipt_id,revision_of,notes
```

最终资产必须逐页匹配 draft 的 `expected_slide_indices`，文件存在、SHA 一致，并由 Pillow 完整解码 PNG/JPEG/GIF/WebP；只伪造文件头不能通过。`render_method` 只允许 `deterministic_layout | manual_design | image_model | hybrid | authorized_capture`。当前 manifest 只保存当前资产，所以 `starter_prompt_sha256` 与 `revision_of` 必须为 `none`；历史修订应在独立不可变生产日志中保存，不能用 unverifiable ID 冒充。缺页、重复页、额外页、跨稿重复 asset ID 或未发布 binding 都阻断 `rendered_pass`。

`rendered_pass` 还要求 `visual-review-receipts.jsonl`。每个当前资产一条，精确字段：

```text
review_receipt_id,draft_id,draft_asset_id,asset_sha256,binding_sha256,slide_index,content_owner_id,reviewer_id,reviewer_independence_status,reviewed_at,feed_review_status,full_review_status,review_status,issues,receipt_sha256
```

`content_owner_id` 与 `reviewer_id` 必须具体且不同，`reviewer_independence_status=independent`，feed/full/final 三项均为 `PASS`，`issues=[]`，日期不得早于 run 且不得晚于今天。`receipt_sha256` 对移除自身后的完整 object 做 UTF-8、key sort、compact JSON SHA-256。模板故意是 `NEEDS_REVIEW` 占位行；替换所有字段并重算 hash 前绝不会放行。

第三方原图只作观察，不进入 image edit/reference；长中文用确定性排版。视觉文件校验依赖 Pillow；缺少 Pillow 时视觉交付 fail closed，copy-only 研究仍可运行。

这些模板默认只有 header 或空 JSONL，不含伪造 evidence。真实 12 帖发布结果、完整场景矩阵和 3 人实图盲评保持 `deferred/incomplete`；不得据此宣称流量或审美效果已验证。

## 引用图

```text
query ──发现──> source/account/post
source ──支持/反证──> claim
query + post ──逐页采集──> style sample/record/library rule
post + claim + account baseline ──约束──> topic
topic + published style binding + truth material ──生成──> brief/prototype/draft
SKU/offer eligibility ──逐surface放行──> channel/draft CTA
adult production-gate receipt ──逐稿放行──> sensitive commercial CTA
```

任何箭头断裂都应报错或降级，不允许用总结文字替代底层行。
