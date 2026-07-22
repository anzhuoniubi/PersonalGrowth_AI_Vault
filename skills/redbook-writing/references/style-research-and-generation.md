# 小红书候选流量密码、风格研究与视觉生产

> 目标：适用于所有类目，从当前站内高/普通/低表现内容中提取可审计的流量机制、载体、视觉和文风假设，再用于选题、成稿与视觉 brief。这里研究的是条件性关联，不是“爆款模板”。

## 1. 先定义“流量第一”

`traffic_first` 不等于“点赞第一”。执行顺序固定为：

```text
合规 / 真实性 / 授权 / 账号安全 hard gate
                    ↓ 通过
自有一方 impressions；平台只给 reach 时固定用 reach
                    ↓
feed CTR、停留：解释看见后是否停下
                    ↓
主页访问率、关注率：解释流量是否属于目标人群
                    ↓
后续转化：另建实验，不反推内容已经有流量
```

- 竞品公开页看不到曝光，只能记录 `engagement_proxy / public_proxy`。
- 点赞、收藏、评论、搜索位置都不能写成“曝光高”或“流量已验证”。
- 自有账号没有 impressions/reach 时，traffic verdict 必须是 `unavailable/insufficient`；CTR、停留、关注和成交都不能顶替曝光。
- 曝光上升但主页访问率或关注率明显下降，标 `broad_low_quality_traffic`，放大决策为 `hold`。

### 五个流量环节

流量密码不是一个扁平标签。每条机制先声明主要作用环节：

| traffic stage | 典型待验证机制 |
| --- | --- |
| `feed_stop` | 身份冲突、结果反差、视觉证据缺口、明确范围承诺 |
| `read_through` | 信息递进、冲突升级、延迟揭晓、逐页新增信息 |
| `save_share` | 清单、比较、步骤、成本、可打印或可信压缩 |
| `comment_cocreation` | 可站队矛盾、可续写语言、个人经验接口 |
| `profile_follow` | 稳定代理 IP、系列承诺、内容与主页一致 |

一条内容可以影响多个环节，但必须选一个 primary stage；其他只作 diagnostics。视觉、标题、正文、评论接口和主页承诺分别归到它真正执行的工作，不能都叫“封面风格”。

## 2. 风格研究的最小单位

不要以“一篇高赞帖”作为风格单位。最小研究包至少包含：

1. 一个目标帖，逐页完整观察；
2. 同账号、同指标、相近年龄的 baseline，目标帖必须排除；
3. 一个真正匹配的普通/低表现对照，或明确标为 boundary；
4. 目标与对照的具体 feature contrast；
5. 载体、primary job、素材条件、权利状态和混杂；
6. 可复算 receipt；缺任一项时保持 `candidate/unverified`。

### 对照类型

| 类型 | 必须相同 | 可以回答什么 |
| --- | --- | --- |
| matched control | 账号阶段、primary job、carrier、题材边界、帖子年龄、商业浓度等预注册维度 | 哪个差异特征值得测试 |
| same-template control | 同账号、同模板、同系列；题目或推进不同 | 模板常量不足以解释表现 |
| carrier boundary | carrier 相同，但 primary job 或题材不同 | 载体可用，不证明表现机制 |
| cross-category analogue | primary job 与信息工作相同，类目不同 | 生产机制的跨类目适配假设 |

required match dimension 为 `unknown` 时，不得称 matched。不同 primary job 的帖子永远只能是 boundary。

## 3. 站内采集顺序

### 3.1 先锁查询与目标工作

每个查询先写：

```text
category × carrier × primary_job × audience_state
query / surface / sort / captured_at
metric definition / baseline window / missing policy
required materials / constraints / contraindications
```

`primary_job` 是硬条件：`feed_stop`、`search_answer`、`explain`、`trust_build`、`decision_support`、`relationship_build`、`conversion`、`authority_statement`。相邻 category 只能作为补采线索和 analogue review，不能进入 production binding；不能为了找到结果而悄悄换 category、job 或 carrier。

### 3.2 保存完整页面，不只看封面

对每个聚焦帖：

- 保存所有当前可见页的 index、尺寸、hash、访问状态和采集时间；
- 轮播必须从 0 到末页，缺中间页即 `partial`；
- 分开记录标题、封面字、逐页字、caption 和 CTA；
- 原图与长文只放私有本地库，Git 只放脱敏 ID、hash 和抽象观察；
- 登录墙、验证码、频率限制出现时保存续跑点并停止，不绕过。

### 3.3 建可比 baseline

同一 performance definition 只能使用同一个 metric 和解析口径。界面显示 `2.7万` 时保留原始字符串、解析版本与近似性质；不得伪装成平台精确值。目标帖及同一 `library_post_id` 的其他 observation 都不得进入 included baseline。

公开竞品可以派生“相对高互动 proxy”；只有自有一方 impressions/reach 才能产生 traffic verdict。

## 4. 逐页观察表

每页先回答“信息工作”，再描述审美：

| 层 | 要记录什么 |
| --- | --- |
| page role | feed stop、场景、证据、步骤、比较、转折、总结或 CTA |
| material | 实拍、界面截图、聊天 UI、文档、产品、插画或 type-only |
| composition | 主体比例、裁切、留白、网格、分屏、满版或自由拼贴 |
| hierarchy | 首焦点、第二焦点、层级数、文字密度、阅读顺序 |
| annotation | 圈、箭头、下划线、荧光、标签；它具体帮助定位什么 |
| imperfection | 模糊、旧照片、自然阴影、杂物、非统一裁切是否承担真实性 |
| image/text division | 图片给证据，文字解释；或图片给结论，caption 补上下文 |
| copy move | 钩子、冲突、展开、证据、转折、payoff、边界、互动 |

不要先填“奶油风、杂志感、高级感”。这些词若不能转成页面工作、素材和注意力路径，就不能指导生产。

## 5. 特征必须分角色

每个视觉或文风特征只能选一种角色：

| 角色 | 定义 | 能否作为表现规则 |
| --- | --- | --- |
| `series_constant` | 高低样本共同存在的系列识别资产 | 否 |
| `task_fit` | 载体/素材与 primary job 相容 | 否，只指导生产选择 |
| `contrastive_performance_hypothesis` | 在合格 matched contrast 中真正不同 | 仅可作为待测表现假设 |
| `anti_pattern` | 在当前任务中会破坏证据、可读性或真实性 | 只能用于排除 |

如果某特征同时出现在高帖与低帖，它必须自动降为 `series_constant`，不能因为目标帖很高就写成“流量按钮”。公开互动对照最多得到 `public_proxy_association`；只有被实际比较的规则在自有一方 impressions/reach 实验中复现，才可在新版本写 `first_party_traffic_validated`。

## 6. 两个重要样本怎样用

### 6.1 苞米谷子：稳定代理 IP，不是“屁股公式”

同账号高低帖都使用单张纯色大字卡、固定引号/短横线、`屁股` 代理人和长 caption，公开点赞仍相差数十倍。由此可以得到：

- 纯色、大字、代理词、长文都是 `series_constant`；
- 可测试的是“固定低防御代理人 × 广泛身份冲突 × 具体人生阶段 × 可被读者续写的同一隐喻语义场”；
- 不复制作者的身体部位、原句、封面或隐喻资产；
- 成人关系账号可以测试物件、身体感受或虚构见证者，但必须明确虚构，不冒充真人投稿或聊天记录。

### 6.2 六周年关系档案：时间证据，不是统一滤镜

18 页关系轮播用多年真实照片形成从戒备到信任的时间链。跨年份素材的清晰度、光线和构图不一致，这种不统一本身就是证据。由此只能得到 `task_fit`：

- 关系档案页要回答“这张图证明了关系的哪个变化”；
- 允许旧照片、模糊、不同设备和不同裁切；
- 轻量文字绑定具体节点，caption 总结关系弧线；
- 没有本人或已授权真实档案时，换成明确虚构、插画或物件代理，禁止用 AI 人像伪造共同生活史。

同账号普通 PLOG 的 primary job 不同，只是 carrier boundary，不是 matched control。

## 7. 从观察到风格规则

规则晋级必须同时满足：

1. visual/copy/metric 来自同一 post observation；
2. support 有完整 baseline、程序派生 tier 和逐页观察；
3. counterexample/boundary 同样绑定自己的 metric，不能跨帖拼证据；
4. 至少两个独立账号和两个非重复 cluster 才能进入 supported；
5. 规则写适用范围、反例、混杂、复核日期和 `performance_evidence_scope`；
6. 只晋级实验里真正被改变、被比较的机制。共同存在的字体、配色或辅助规则不得搭便车；只有交互效应时，晋级组合规则而不是分别晋级两个主效应。

无完整 receipt 的高赞帖可以启发查询，但不能让 draft 变成 ready。

## 8. Draft 检索与 ready 门

检索顺序：

```text
exact category + exact carrier + exact primary_job + constraints/materials
→ 没有 exact published rule：needs_style_research
→ 可另搜相邻 category 形成 analogue research lead，但不得绑定到当前 draft
```

不得放宽 category、primary job 或 carrier，不得混入 contraindicated 素材。`series_constant` 和 `task_fit` 可作为身份/生产辅助，但 `traffic_first` 的 primary performance rule 必须是 contrastive hypothesis。只有 `first_party_traffic_validated` 才能写“已验证流量”，但当前 release gate 整体禁用该 scope；`public_proxy_association` 必须明确是公开互动关联。

没有 qualified rule 时：

- 输出缺口、补采 query、需要的真实素材和测试方案；
- 只有绑定至少 2 条 task-fit 机制、1 条反例/anti-pattern，且事实、授权和真实性门通过时，才可以给 `candidate_only / needs_review` 的标题、完整候选文案、逐页结构与探索 brief；
- 若生成探索图像，真实素材与权利必须满足，且状态最多为 `prototype_only`；不得用 AI 图、伪截图或临时仿版补造证明素材。`rendered_needs_review` 仅用于已经有 published binding、已生成最终逐页文件但尚未取得独立人工 PASS receipt 的情形；
- 不得称 ready、可直接发布或爆款公式；
- 不得为了交稿跳过检索，或用单篇截图临时造母版。

## 9. 视觉 brief：先页面工作，后风格词

封面请求先加载 [cover-pattern-library.md](cover-pattern-library.md)：用 `visual_evidence_role` 决定文字还是证据先工作，再进入下述 brief。字卡是文字型任务的条件默认，不是全类目默认；任何实拍、before/after、截图、文件、质地或比较作为第一证据时，都必须让真实素材先出现。

Brief 至少包含：

```text
functional_need × lived_scene × motive × perceivable_outcome
primary_job / carrier / audience_state
真实可用素材与禁止生成的证据
两条概念不同的 attention path
逐页 role 与 image/caption division
绑定规则、counterexample 与 intentional deviation
```

### 不是 PPT 的判断

不要机械禁止网格、深蓝、圆角或品牌色。判断它们是否执行当前任务：

- 搜索教程、比较决策、法律清单和权威说明可以严格网格；
- 关系故事、生活档案、真实体验不应被统一卡片和企业 KV 吞掉；
- 同一圆角卡、三条 bullet、渐变背景和图标矩阵反复出现，却没有具体素材工作时，才是通用 AI PPT 风险；
- 便签、手写、荧光笔也不是“小红书味”默认项，没有信息任务同样删除。

### 概念原型

有两个证据充分的合格方向时，做两个注意力路径真正不同的可查看原型，例如“真实证据先行”与“冲突命题先行”。只换配色、字体或标题不算第二概念。exact cell 只有一个合格探索方向时最多做一个 `prototype_only`，不为凑数自创第二方向，也不能声称已完成比较；没有方向才停在 `prototype_gap / brief_only`。先看双列 feed 缩略图，再看全尺寸；记录选中/淘汰理由后，只扩展有依据的方向。

用户连续两次评价整体“丑、不像小红书、方向不对”时，停止微调。新 brief 必须在目标、参考集合、注意力路径三类中至少改变两类，再渲染。

## 10. 文风生产

文风也按功能拆，不抄口头禅：

- 标题只建立一个缺口、冲突或明确收益；
- 开头第一屏兑现标题，不先铺背景；
- 每个抽象判断至少落到一个动作、物件、对话选择或结果；
- 关系故事用选择与后果推进，不用营销号总结替代事件；
- 聊天载体只能来自本人、明确授权或显著标注的虚构；
- caption 与图片分工，避免逐字复述；
- 互动问题应让读者补充经验或边界，不诱导刷词、私信或外链。

## 11. “代理人 × 标题框架”12 帖实验

这是一个小样本、分块 2×2 探索，不是平台因果实验：

| block 主题 | A1 代理叙事 × B1 身份冲突 | A1 × B2 日常解释 | A2 直接叙事 × B1 | A2 × B2 |
| --- | --- | --- | --- | --- |
| 欲望差异 | 1 | 2 | 3 | 4 |
| 拒绝/边界 | 5 | 6 | 7 | 8 |
| 身体羞耻 | 9 | 10 | 11 | 12 |

发布前冻结：随机种子、计划顺序、时间窗、每格 proposition hash、carrier、视觉生产类型、证据深度、CTA、商业浓度、held constants hash 和允许偏离原因。首轮不放成人商品 CTA，只验证获客载体；商业承接另开实验。

每格在预注册的同一 checkpoint 记录同一个一方 exposure primary（impressions 或 reach），以及 CTR/停留、主页访问、关注、隐藏/举报/审核等诊断。checkpoint 由内容生命周期、平台数据可得性和账号基线决定，不把 24h/72h 当跨类目默认。不允许因为前几篇先高就提前停；只有合规、真实性、授权或账号安全 hard gate 可以停止。

放大至少满足：3 个主题中 2 个同方向、没有严重反向 block、质量 guardrail 未显著退化、全部 hard gate 通过。否则保持 directional/inconclusive。

## 12. 命中成人亲密关系或成人商品时的额外门禁

任何故事、画面和 CTA 逐项检查：

```text
purpose → audience safety → expression → authenticity/consent
→ account/surface rule → SKU/commercial eligibility → disclosure
```

- 成人用品、避孕与防护等商业内容必须按当前具体账号、SKU、surface 和合作方式重新核验，不能从“关系教育可以发”推导“商品可以卖”。
- 未核清前内容与商品实验分离；流量测试不加商品暗号、私信诱导或二维码。
- 不用擦边、伪投稿、假聊天、假测评和 AI 真人经历换曝光。
- hard gate 失败永远优先于流量结果。

## 13. 每次产出的完成条件

- 结论能回到具体 observation、baseline、对照和逐页记录；
- 高低共同特征没有被写成表现机制；
- public proxy 没有被写成真实流量；
- draft 绑定 exact carrier/job/constraints/materials；
- 两个原型真实可看，feed/full review 有记录；
- 真实素材、授权、虚构披露和成人商业门禁已核；
- 缺证据时状态停在 `candidate / needs_style_research / needs_review`，不伪装 ready。
