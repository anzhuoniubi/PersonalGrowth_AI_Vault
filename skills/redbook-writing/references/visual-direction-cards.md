# 跨类目视觉方向卡 v1.1

机器资产：`assets/visual-direction-cards-v1.json`

选择器：`scripts/select_visual_directions.py`

这 16 张卡只回答两个问题：第一份真实证据怎样进入首屏；不同载体怎样安排证据、动作与边界。它们不回答“什么配色会爆”，也不提供字体、滤镜、裁切、标注或密度公式。

全部方向卡固定为：

```text
maturity                   = prototype
performance_evidence_status = candidate_only
performance_evidence_scope  = not_performance_evidence
starter_eligible            = false
aesthetic_authority          = published_style_binding_only
```

## 目录

- [1. 生产态选择合同](#1-生产态选择合同)
- [2. 方向卡索引](#2-方向卡索引)
- [3. 素材 manifest](#3-素材-manifest)
- [4. 风格 binding](#4-风格-binding)
- [5. 载体角色与单图合并](#5-载体角色与单图合并)
- [6. Prompt 变量合同](#6-prompt-变量合同)
- [7. 失败状态](#7-失败状态)
- [8. 审稿边界](#8-审稿边界)
- [9. 证据与晋级](#9-证据与晋级)

## 1. 生产态选择合同

按以下顺序运行，不从卡名倒推素材：

1. 写定本篇 exact `category`、唯一 `primary_job` 和 exact `carrier`。
2. 把真实素材、事实收据、人工审校和授权证明写入 `asset_manifest_refs`。
3. 运行选择器；只保留任务、载体、全部必需素材、素材数量门槛同时满足且未命中 contraindication 的卡。
4. 在生产态提供 v2 style-library SQLite 与已经发布的 `draft_binding_id`。选择器从数据库回链 archetype、rules 和 publication hashes；方向卡只控制 evidence/attention skeleton，binding 控制审美。
5. 若返回 `no_eligible_card` 或 `prototype_gap`，补真实输入或换载体，不让生成模型补图、补聊天、补过程、补效果或发明“类似风格”。

```bash
python3 redbook-writing/scripts/select_visual_directions.py \
  --category software-tutorial \
  --job search_answer \
  --carrier screenshot_markup \
  --asset-manifest run/asset-manifest.json \
  --style-library run/style-library.sqlite \
  --draft-binding-id DSB-20260718-001 \
  --json
```

探索态可在没有 binding 时查看候选骨架：

```bash
python3 redbook-writing/scripts/select_visual_directions.py \
  --category relationship \
  --job relationship_build \
  --carrier chat_dramatization \
  --asset-manifest run/asset-manifest.json \
  --mode exploration \
  --json
```

探索结果固定为 `prototype_only`；只有显式 exploration 可以把候选卡当作单一探索方向，仍不能标为 ready 或回写成表现规则。

需要在主验证器中复用时，调用 `select_from_paths(...)`；不要自己读取 JSON 后传一个可任意指定的 asset root。该 API 会从 manifest 文件路径派生 root，并复用与 CLI 相同的文件、DB publication 和 exact-match 检查。`load_published_style_binding(...)` 可单独用于核验一个 DB binding receipt。

## 2. 方向卡索引

| 卡 | 载体入口 | 可解决的任务 | 第一份证据 | 最近替代思路 |
|---|---|---|---|---|
| VDC01 真实改造 | 实拍日记 / 照片批注 | 信任、决策 | 完整真实起点与过程 | 只有使用结果时转 VDC09 |
| VDC02 工作物首屏 | 照片批注 / 清单步骤 | 搜索、权威 | 当前文件或工具 | 工作物不可公开时转 VDC11 |
| VDC03 截图教程 | 截图批注 | 搜索 | 同版本连续截图 | 动态路径必要时转 VDC15 |
| VDC04 产品比较 | 比较警示 / 实拍日记 | 决策、转化 | 多候选与统一协议 | 无统一协议时转 VDC09 |
| VDC05 复杂解释 | 文字卡 / 照片批注 | 解释、权威 | 当前一手来源与答案图 | 单个工作物足够时转 VDC02 |
| VDC06 关系档案 | 拼贴日记 / 实拍日记 | 关系、信任 | 全员授权档案与时间线 | 档案不完整时转 VDC12 |
| VDC07 系列代理 | 文字卡 / 单图 / 拼贴 | 停留、关系 | 自有代理与本篇新事实 | 无自有代理时转 VDC10 |
| VDC08 场景路线 | 照片批注 / 拼贴 / 实拍 | 搜索、决策 | 核验路线与当前信息 | 路线素材不可用时转 VDC11 |
| VDC09 真实体验 | 实拍日记 / 照片批注 | 信任、转化 | 到手与真实使用 | 多候选统一协议时转 VDC04 |
| VDC10 视觉反证 | 照片批注 / 单图 / 实拍 | 停留、关系 | 授权且无伤害的反证画面 | 有伤害风险时转 VDC12 |
| VDC11 清单工作表 | 清单 / 文字卡 / 单图 | 搜索、决策 | 已审校行动与来源 | 必须看真实对象时转 VDC02 |
| VDC12 氛围+实用出口 | 实拍 / 拼贴 | 关系、信任、转化 | 授权真实处境 | 核心为产品体验时转 VDC09 |
| VDC13 聊天叙事 | 聊天演绎 | 关系、信任、停留 | 授权原始聊天或显著虚构标签 | 无授权时转 VDC12/VDC11 |
| VDC14 过程视频 | 过程视频 | 信任、解释、决策 | 真实动作序列 | 只有照片时转 VDC01 |
| VDC15 录屏教程 | 屏幕录制 | 搜索、解释 | 当前版本录屏与验证结果 | 静态足够时转 VDC03 |
| VDC16 口播/现场 | 真人或现场视频 | 解释、信任、权威 | 真人/场地授权与主张依据 | 来源复杂时转 VDC05 |

`VDC07` 是 `series_modifier_only`。即使已经有 published binding，也必须同时存在一个完成本篇任务的基础方向；系列代理不能单独成为生产方向。

## 3. 素材 manifest

每条 `asset_manifest_ref` 都要有以下字段；字段存在不等于审核通过，值也必须满足合同：

```json
{
  "asset_id": "screen-01",
  "asset_path": "assets/screen-01.png",
  "material_codes": ["current_owned_screen_captures", "verified_path"],
  "sha256": "64 位小写十六进制哈希",
  "media_dimensions": {"width_px": 1170, "height_px": 2532},
  "rights_basis": "owned",
  "authorization_ref": null,
  "license_ref": null,
  "transform_history": [],
  "privacy_review": "redacted",
  "commercial_disclosure": "not_applicable",
  "expires_at": null
}
```

执行这些约束：

- 以 manifest 文件所在目录为唯一 locator root；`asset_path` 必须是 root 下的相对路径。
- 拒绝绝对路径、`..`、不存在/非普通文件、解析到 root 外的路径，以及指向 root 外的 symlink。
- 打开真实文件重新计算 SHA-256；自报哈希与文件不一致时，在选择前失败。
- 按文件签名和扩展名识别视觉媒体；PNG/JPEG/GIF/WebP 读取文件头校验宽高，MP4/MOV/M4V/WebM 用 `ffprobe` 校验。视觉文件改成 `.txt` 也不能绕过；视觉文件不允许把 `media_dimensions` 写成 null。
- `rights_basis=written_permission` 时填写 `authorization_ref`。
- `rights_basis=licensed` 时填写 `license_ref`。
- 保存裁切、遮罩、去标识、调色和合成等变换记录；空数组只表示没有变换。
- 把隐私和商业关系分别审查，不用“已授权”代替隐私或广告披露。
- 对界面、价格、路线、营业、版本等会过期的信息填写 `expires_at`；过期 receipt 不参与选择。
- 按 `distinct_asset_id` 计算素材数量；把同一文件复制多个文件名不能通过 count gate。

Manifest 可以同时容纳照片、视频、界面、来源文档、授权单和人工审校记录。每条 receipt 必须能定位到真实本地文件并重算哈希，避免模型凭一个自然语言素材名宣称“已经有证据”。

当前选择器只接受本地文件 locator。不要把对象存储 URL、网盘分享链接或数据库 URI 填进 `asset_path`。如果未来确需非文件源，先定义独立的 `verified_private_locator` provider、鉴权范围、不可伪造的 `verification_receipt` 与内容哈希回执，再扩展 selector；裸 URL + 自报 hash 不合格。

## 4. 风格 binding

生产态必须使用 `--style-library <sqlite> --draft-binding-id <id>`。不再接受 standalone style-binding JSON，因为 `"status": "published"` 和一个自报 hash 不能证明它来自已发布库。

选择器以只读方式打开 `PRAGMA user_version=2` 的数据库，并完成以下回链：

```text
draft_style_bindings
  → draft_binding_publications
  → style_archetypes + archetype_publications
  → selected_rule_ids
  → archetype_rules + archetype_rule_publications
```

它会重新计算 archetype snapshot hash、draft binding hash 和每条 selected rule hash，要求 binding 为 `review_status=PASS`、archetype 为 `supported/reusable`、rules 为 `active` 且全部已有 publication。`category + primary_job + carrier` 三项必须与 archetype 精确相等；不做“大类相近”“all category”或 carrier 降级。

生产态的最终 aesthetic contract 只从已发布 rule payload 中提取 `palette`、`typography`、`image_treatment`、`density`、`annotation_language`、`crop_logic`。任一字段缺少已发布 rule receipt，都返回 `prototype_gap`，不会从方向卡补齐。唯一的探索例外来自独立的 `aesthetic-exploration-prompts-v1.json`：无 binding、显式 `explicit_exploration`、exact scope cell、真实素材/权利/约束全部闭合时，可以叠一条带 source/prompt hash 的 AP overlay，输出上限仍是 `prototype_only`。AP 不改变本卡 `aesthetic_authority=published_style_binding_only` 的生产权限，也不能进入最终 binding。

权限边界必须清楚：

| 方向卡控制 | Published style binding 控制 |
|---|---|
| 注意力路径 | 色彩与明暗关系 |
| 证据到达顺序 | 字体、字号层级、字重 |
| carrier role plan | 裁切与图像处理 |
| 图像/页文/caption 分工 | 标注语法与装饰语言 |
| 真实性、权利、隐私、披露边界 | 密度与系列识别常量 |

不要把方向卡里的 prompt 当作审美 system prompt。没有 exact、数据库可回链的 published binding 时，方向卡单独使用仍应停在 `prototype_gap`；只有上述独立 AP selector 返回 `matched_exploration` 时，才可做一次 `prototype_only` 粗原型。不要从卡名、类目印象或模型偏好临时发明色板。

## 5. 载体角色与单图合并

每张卡对每个可用 carrier 都有独立 `carrier_role_plans`，不要把轮播页序直接套到视频或单图：

- 轮播：每页完成一个证据、动作、判断或边界；只合并因果相邻且仍能辨认的角色。
- 聊天：先显示真实授权/虚构演绎标签，再给处境、关键来回、转折和行动；聊天气泡不能承载作者旁白。
- 过程视频：真实对象与动作先于剪辑节奏；补拍、演示、变速和时间线重排必须披露。
- 录屏：目标结果、版本、定位、动作、验证、异常分支形成同一版本闭环。
- 口播/现场：人负责提出有边界的判断，来源、对象和演示负责证明；字幕不能代替依据。
- 单图：只允许“主证据 → 判断/行动 → 来源/披露/边界”的可扫描合并；不得把整套轮播缩成微型卡片，也不得靠缩小字号补齐。

每个 carrier 另有 `material_count_gates`。例如连续截图、比较对象和关系档案需要多条可区分素材；选择器按不同 `asset_id` 计数，不按文件名或材料标签重复计数。

## 6. Prompt 变量合同

`prompt_variables` 不再是字符串清单。每个变量必须声明：

```text
name | type | required | null_behavior
```

执行规则：

- `required=true` 时固定 `null_behavior=block_selection`。
- 每个 `page_roles.required_proof` 和 `carrier_role_plans.roles.required_proof` 都必须有同名必填变量。
- `asset_manifest_refs` 始终必填。
- `published_style_binding_id` 在静态候选卡中可空，但空值触发人工检查；生产选择器只会用 SQLite reconciliation 得到的 binding ID 填入。
- 可选变量只能使用 `omit_clause`、`render_as_not_applicable` 或 `require_human_review`；禁止让模型猜一个默认值。

Prompt 输出回显：已用 asset ID、未用原因、逐角色 proof job、copy job、caption job、缺失项、授权、隐私、商业披露和人工审稿点。输出不得自行升级为 ready。

## 7. 失败状态

| 状态 | 含义 | 正确动作 |
|---|---|---|
| `invalid_query` | category 为空，或 job/carrier/contraindication 不在 taxonomy | 修正输入，不做近似匹配 |
| `invalid_asset_manifest` | 文件 locator、SHA、尺寸、权利、授权/许可、变换、隐私、商业或有效期不合格 | 修文件/receipt 或换素材 |
| `no_eligible_card` | exact 卡存在但缺素材、数量不足或命中禁忌；或没有 exact job+carrier | 补真实输入、换 carrier 或按 nearest alternative 重做任务 |
| `prototype_gap` | 骨架可用，但缺 SQLite 可回链且 exact category/job/carrier 的 published binding；或系列卡会成为唯一生产方向 | 发布/修复 DB binding 或增加基础方向 |
| `matched_exploration` | 仅允许验证候选骨架 | 保持 prototype_only，不发布 ready |
| `matched` | 素材和 binding 合同通过 | 仍需事实、视觉、权利与发布前人工审稿 |

选择器不会把“差一点匹配”的结果返回为合格 production binding。相邻类目只能登记为补采线索或 analogue review；最终 style binding 与一次性 AP scope cell 都不得自动放宽 category、任务、载体、素材真实性或权利。

## 8. 审稿边界

### Feed 缩略图

- 第一眼能否认出对象、任务和第一份证据；
- 标题是否只做承诺，不遮住证据；
- 人物、颜值、争议、品牌或产品是否抢走本篇 primary job；
- binding 的视觉语言是否真的来自已发布样本，而不是方向卡或模型默认审美。

### 全尺寸 / 播放态

- 每个页面或镜头是否新增一个证据、动作、判断或边界；
- 每个结论能否回指 manifest receipt；
- 版本、授权、隐私、商业披露和有效期是否可见；
- 视频时间线、变速、补拍和演示是否造成虚假因果；
- 图片、页文、字幕与 caption 是否分工，而不是逐字重复；
- 缺失项是否保持缺失，是否被设计润色成“仿佛已经证明”。

判断 AI PPT 化时，不寻找某个固定风格。检查：真实素材是否在做信息工作；载体角色是否闭环；删掉装饰后，证据、动作和边界是否仍成立。

## 9. 证据与晋级

方向卡只允许三种证据角色：

- `task_fit`：素材和载体适合完成任务，不是表现规则。
- `series_constant`：帮助识别账号，但高低帖共有时不能解释表现。
- `candidate`：注意力顺序或证据距离需要同账号、同任务、同 carrier、相近阶段的一方数据继续验证。

卡片本身永不升级为 starter 或表现规则。取得合格配对与一方实验后，把新 observation、rule、archetype 和 binding 发布进 append-only style library；保留这份静态候选卡的 `candidate_only` 边界，不回写成“已验证爆款模板”。

参考样本统一为 `reference_only_no_reuse`。只迁移抽象任务机制，不复制图片、原句、人物、代理 IP、产品组合、路线、表格、色板、构图、镜头或页面顺序。公开赞藏评没有曝光分母，不能成为 traffic verdict；服务商或官方生产建议能证明工作流，不自动证明自然推荐因果。
