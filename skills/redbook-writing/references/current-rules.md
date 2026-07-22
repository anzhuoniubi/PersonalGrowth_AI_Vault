# 当前规则、敏感内容与商业资格

本地快照：2026-07-16。规则页面会更新，本文件不是永久通行证。任何涉及身体/性、医疗、未成年人、利益关系、导流、商品、广告、专业号、店铺或个人敏感信息的任务，都要在运行时重新打开当前官方页面，记录 URL、页面日期、访问日期、作用域与原意。

导航：[核验顺序](#规则核验顺序) · [一手来源](#当前一手来源索引) · [六道门](#敏感内容六道门) · [真实性](#真实性与-ai改编标签) · [SKU](#成人用品必须具体到-sku--account--surface) · [最终记录](#最终规则检查记录)

## 规则核验顺序

```text
全站社区与真实性
→ 内容表达与安全
→ 商业合作内容
→ 广告/线索产品
→ 专业号行业准入
→ 店铺/商品类目与资质
→ 具体SKU、素材、落地页和交易链路
```

上一层通过不能替代下一层。自然内容、蒲公英、广告、专业号、店铺、私信/留资和官方外跳是不同 surface；必须逐一核验。

核验结果只允许：

- `PASS_SCOPE_ONLY`：当前官方原文在该精确作用域明确通过。
- `NEEDS_PLATFORM_CONFIRMATION`：规则缺失、页面失效、词义冲突、SKU/素材/主体不清。
- `BLOCKED_SAFETY`：未成年人、胁迫/暴力、健康危机、隐私求助或其他安全门不通过。
- `BLOCKED_RULE`：当前官方规则明确禁止。

不要用“看起来很多账号都在做”覆盖规则，也不要把平台暂未处罚当许可。

## 当前一手来源索引

| ID | 作用域 | 2026-07-16 可支持 | 原件 |
|---|---|---|---|
| OFF-010 | 社区公约2.0 | 真实原创、AI辅助标明；不得虚构情感经历等人设；身体/性公共利益表达仍需克制 | [官方帮助页](https://pgy.xiaohongshu.com/help/detail?id=1eda0a065dd894063c2e029a49e8f6a1&userType=4) |
| OFF-007 | 社区规范（2021版仍由官方链接指向） | 禁色情低俗、情色小说、性暗示、虚假体验、机器批量、刷量和站外导流 | [官方协议页](https://agree.xiaohongshu.com/h5/terms/ZXXY20221213003/-1) |
| OFF-005 | 蒲公英商业内容；页面 2026-07-15 更新 | 低价值聊天跟读、空泛两性鸡汤、AI批量/虚构故事起号、模板故事营销、性联想表达与导流风险 | [内容审核规范](https://pgy.xiaohongshu.com/help/detail?id=6495c527d1eedeeb48fb18b1f875650e&userType=4) |
| OFF-011 | 虚假/低差营销 | 虚构故事、伪造测评、冒充权威、夸大效果、标题党、生硬植入、同质模板及处置 | [治理公告](https://pgy.xiaohongshu.com/help/detail?id=a76a1444fd620a8f78d662829ae736a0&userType=4) |
| OFF-012 | 商业合作低差治理 | 虚假评价、生硬创作、低劣画风可能无法发布/投放/使用薯条 | [治理规则](https://pgy.xiaohongshu.com/help/detail?id=bca8cfe9df181853ae4dfe8216299a3b&userType=4) |
| OFF-013 | 流量作弊 | 真实用户正常连续点赞不自动伤号；假账号、互赞、利益诱导、买量水军有风险 | [官方界定](https://pgy.xiaohongshu.com/help/detail?id=8a21bcdf150457ddc168c4cc4b326156&userType=4) |
| OFF-015 | 蒲公英导流 | 二维码、电话/邮箱/微信及“看主页/DD/看置顶”等间接导流被列明 | [导流规则](https://pgy.xiaohongshu.com/help/detail?id=d2027d1aa0ed8b75e76da4c2ca762e2d&userType=4) |
| OFF-019 | 商业竞争/评论 | 竞品笔记评论区招揽、私信竞品意向用户属于商业撬客 | [治理公告](https://pgy.xiaohongshu.com/help/detail?id=8c0b127f03a949d71f1f218a55e7d7f6&userType=4) |
| OFF-004 | 专业号行业准入 | 同页把“性玩具”列禁入，同时注“情趣用品、计生用品”普通准入；具体分类必须平台确认 | [专业号规则](https://ad.xiaohongshu.com/next_help/docs/195c5fe505c71b4b0335a2fe0d61d8e0) |
| OFF-006 | 商家资质历史/当前 PDF | 商业体系存在成人/情趣/计生类目及资质表；需结合列标题和后台当前类目 | [官方PDF](https://picasso-static.xiaohongshu.com/test/8b3bc7324ca06fceea379177f9eed1fa/%E5%B0%8F%E7%BA%A2%E4%B9%A6%E8%B5%84%E8%B4%A8%E5%85%A5%E9%A9%BB%E8%A6%81%E6%B1%82.pdf) |
| OFF-017/021 | 商业产品入口 | 搜索广告、品牌专区、私信/客资入口存在；不证明具体行业/SKU有权限 | [商业产品](https://e.xiaohongshu.com/m/product)、[聚光帮助中心](https://ad.xiaohongshu.com/next_help/home) |

来源等级为 A 只说明原件可靠，不说明能跨作用域外推。例如蒲公英规则不能自动替代自然内容规则；专业号准入不能替代店铺或广告审核。

## 敏感内容六道门

对每个选题、画面、对话、产品主张和 CTA 分别过门，不能只给整篇一个总分。

| 门 | 必查问题 | 阻断/升级条件 |
|---|---|---|
| `purpose` | 是经验、关系教育、医疗公益、新闻讨论，还是猎奇/营销？ | 用性、出轨、羞耻、创伤或隐私尴尬作刺激钩子；“科普”只是包装 |
| `audience_safety` | 可能触达未成年人吗？有胁迫、暴力、健康危机、自伤或求助吗？ | 收集未成年人敏感经历；在危机/求助场景转销售；缺安全资源 |
| `expression` | 有裸露、凸显敏感部位、抚摸、类生殖器、动作暗示、挑逗或不必要联想吗？ | 打码、谐音、emoji 不能自动放行；需按实际画面/语义判断 |
| `authenticity` | 经历、聊天、身份、体验、数字和专家观点从哪里来？ | 伪真人投稿、假聊天、假测评、假人设、无授权截图、AI故事冒充事实 |
| `commercial` | 有无利益关系？主张真实吗？适合/不适合谁？ | 伪素人、生硬植入、功效绝对化、置顶评论打配合、隐藏经营身份 |
| `sku_and_transaction` | 后台实际类目、资质、素材和可用链路是什么？ | 术语冲突、SKU未给、工单缺失、一个surface通过却扩展到另一个 |

任何一门不通过：停止“可发布/可售”结论。可以继续做非商业研究、风险说明或补证清单。

## 成人亲密关系内容

允许进一步评估的编辑载体：

- 经本人明确授权并去身份化的真实案例拆解。
- 明确标注的匿名改编或多案例合成，且不补写关键事实。
- 明确标注“情境演练/虚构”的教育性对话。
- 非露骨的关系、同意、边界、安全、求助与有权威来源的健康教育。

不能进入可发布稿：

- “假装后台投稿/闺蜜故事/亲身经历”的虚构叙事。
- 色情网文、猎奇聊天记录、隐私尴尬、出轨羞辱或性暗示作点击钩子。
- 未经同意展示头像、姓名、账号、单位、地址、医疗或性相关信息。
- 用“仅限18+”替代未成年人安全设计。
- 把一般沟通建议包装成医疗诊断或治疗。

故事与商品默认分轨。若故事天然承担卖货钩子、正文植入产品或评论承接购买，即按商业轨最严规则审核，不能靠“这是虚构文学”降级。

## 真实性与 AI/改编标签

写前从唯一词典选一个 `truth_label`：

| truth_label | 最低证据 | 可做 | 不可做 |
|---|---|---|---|
| `first_person_documented` | 发布主体亲历；涉及他人时有可追溯授权 | 按可证事实叙述 | 补写未提供的细节；扩大用途 |
| `authorized_anonymized` | 同意、用途、范围、撤回与去身份化记录 | 按授权范围匿名整理 | 改变核心事实或暗示逐字原样 |
| `authorized_adaptation` | 有真实材料与改编许可，列出改动 | 合并非关键细节并披露 | 伪造结果或改变核心因果 |
| `composite_cases` | 多份合法材料，明确“合成” | 教育性展示共性 | 让读者以为一个真人经历全部事件 |
| `fictional_scenario` | 无真人暗示，首屏/正文清晰标虚构 | 非情色关系短篇、沟通练习 | 暗示“根据真实投稿”；假测评/假体验 |
| `factual_explainer` | 权威来源与更新时间 | 限定作用域的知识 | 无来源的医疗/功效结论 |

另填 `commercial_relationship` 与实际披露位置；它和 `truth_label` 是两个维度。品牌合作、赠品、佣金、自有商品或受委托创作不能混入真实性标签，也不能用“真实经历”代替利益披露。

AI 参与不改变事实责任。不得让模型补齐日期、对话、症状、身份、产品参数、专家头衔或效果数据。

## 未成年人、危机与求助

- 公开内容按可能被未成年人看到来设计，避免露骨画面、动作教学与不必要的商品刺激。
- 不主动收集未成年人亲密/性/健康投稿。
- 涉及胁迫、暴力、性侵、健康危机、自伤或隐私泄露时，优先提供经核实的当地求助/医疗/法律资源；避免越权诊断。
- 不在这些帖子、评论或私信中引入商品、折扣、主页或咨询线索。
- 无法确认地区或紧急程度时，用保守安全语言并建议联系本地紧急/专业资源。

`audience_safety` 失败直接标 `BLOCKED_SAFETY`，不因为其余五门通过而放行。

## 成人用品：必须具体到 SKU × account × surface

“成人玩具”“情趣用品”不是可审核的 SKU 描述。先收集：

```text
品牌、型号、形态、材质、功能、包装
说明书、禁忌、清洁/兼容、真实体验
主体与类目资质、物流、私密包装、卫生退换、售后
拟用画面/文案、平台、surface、落地页、CTA
后台类目截图或平台工单及日期
```

至少拆这些 surface：

```text
organic_content
professional_account
shop
pgy_commercial_content
ads
leadgen
dm_commercial
approved_external_destination
```

每一项在 `sku-registry.csv` 单独记录。允许 CTA 的必要条件：

```text
具体SKU资料完整
AND 本次运行采集的当前官方精确工单/审批记录
AND 账户/主体/行业资格
AND 素材ID及其SHA-256与获批版本一致
AND sku_eligibility/offer_eligibility 主张完整绑定SKU/offer、平台、账号、surface和素材哈希
AND 素材与功效证据
AND 当前surface状态 confirmed/approved
AND 目的地与交易/隐私流程通过
```

任一为 unknown/expired/needs confirmation/rejected：对应渠道保持 blocked。`OFF-004` 的术语冲突不能当作文字漏洞；不得自行把“性玩具”改名为“情趣用品”以绕开分类。

## 商业真实性、广告与功效

平台规则之外，再检查现行法律；执行时复核适用法域：

- [互联网广告管理办法](https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_d93a579afd45413e8576e4623fab348f.html)（LEG-004）：体验/测评附购买方式时需具广告可识别性，不得欺骗点击。
- [广告法](https://www.npc.gov.cn/npc/c1773/c1848/c21114/c25274/c25277/201905/t20190521_207459.html)（LEG-005）：性能、用途和效果应真实；非医疗商品不得混淆疾病治疗，且需保护未成年人。

每项产品/功效主张记录：原始资料、证据类型、适用条件、不适用对象、未知项、最后复核日期。没有证据就删除或改为可验证的参数描述；“用户都说”“医生推荐”“绝对安全”“修复关系/治疗问题”等不能凭模型生成。

## 投稿与敏感个人信息

[个人信息保护法](https://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html)（LEG-003）要求敏感信息处理有特定目的、充分必要和严格保护，通常需单独同意。亲密投稿常包含身份、健康、性取向、聊天和交易信息，至少建立：

- 明确用途、公开范围、改编范围和授权主体。
- 可撤回机制与撤回后的删除/停止使用流程。
- 最小收集、去标识、访问权限、加密/备份与保留期限。
- 聊天双方权利、第三方信息和截图平台条款。
- 未成年人排除与危机升级流程。

不要把原始私密聊天、身份证明或医疗材料直接喂给不必要的工具；先去身份化，且只保存完成任务所需字段。

## 最终规则检查记录

每篇敏感/商业稿附：

```text
gate: purpose/audience_safety/expression/authenticity/commercial/sku_and_transaction
status: PASS_SCOPE_ONLY | NEEDS_PLATFORM_CONFIRMATION | BLOCKED_SAFETY | BLOCKED_RULE
source_ids + exact URLs
page/version date + checked_at
scope/platform/account/surface/SKU-or-offer/source_asset_id/source_asset_sha256/platform_ticket/qualification_claim_id
remaining unknowns
human/platform confirmation needed
```

只要页面缺失、措辞冲突或资格过期，就输出“需要平台确认”，不要写“可以发”“可以卖”。
