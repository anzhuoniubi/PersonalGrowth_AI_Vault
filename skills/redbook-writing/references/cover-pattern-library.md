# 小红书原生封面模式库

> 目标：在写视觉 prompt 之前，先决定首屏应该让文字还是证据画面工作。机器资产是 `assets/cover-patterns-v1.json`；当前最高证据资格为 `task_fit`，没有任何模式被声明为流量因果。

## 1. 先选“谁是第一份证据”

```text
这篇内容的第一份可核验证据是什么？
├─ 一个命题、冲突、判断或问题 → 文字先行
│  └─ visual_evidence_role = none / supporting
└─ 人、场景、结果差、UI 路径、文件、质地或比较 → 证据先行
   └─ visual_evidence_role = primary
```

文字先行不是“所有类目统一大字报”。它只在 `text-first job + 无必须首屏展示的视觉证据` 时获得条件优先级。真实画面是第一份证据时，继续用字卡会拉长承诺—证据距离。

## 2. 十三种可检索模式

| ID | 封面模式 | 适合的第一屏任务 | 必需的真实输入 | 典型误用 |
| --- | --- | --- | --- | --- |
| `CP01` | 黑底单命题强调字卡 | 一句话观点、权威判断、冲突命题 | 已核验命题或有来源的本人表达 | 有 before/after 却只写大字 |
| `CP02` | 轻纸张问题梗图字卡 | 问题、困惑、关系张力 | 已核验命题；梗图/物件若出现须自有或授权 | 随机贴图只负责“可爱” |
| `CP03` | 荧光便签人话字卡 | 口语命题、成长/关系随笔 | 已核验命题或授权经历 | 把便签、手写、荧光当原生感 |
| `CP04` | 真实主体实拍 + 稀疏标题 | 在场、人物状态、生活体验 | 自有或授权实拍 | AI 场景冒充经历、文字遮挡证据 |
| `CP05` | 真实前后结果对照 | 变化、效果、改造、决策 | 可比的真实 before/after | 不同光线/角度制造假变化 |
| `CP06` | 截图 / 文件证据批注 | 教程路径、法律/流程证据 | 自有 UI 截图或授权文件节选 | 伪 UI、泄露隐私、无意义红框 |
| `CP07` | 清单 / 表格 / 比较网格 | 搜索答案、保存、比较 | 已核验清单或统一比较协议 | 把企业 PPT 缩小塞进封面 |
| `CP08` | PLOG / 时间档案拼贴 | 关系、旅行、Vlog、时间变化 | 自有或授权的多场景档案 | 没有叙事关系的素材堆砌 |
| `CP09` | 产品 / 质感 / 上手特写 | 质地、尺寸、适配、使用关系 | 自有/授权细节或统一比较 | 只有精修 packshot，没有证据 |
| `CP10` | 授权对话 / 明示演绎首帧 | 关系冲突、对话张力 | 授权原始对话或首屏明示虚构、脱敏和场景范围 | 假聊天伪装真人投稿 |
| `CP11` | 真实动作过程视频首帧 | 制作、改造、测试、操作 | 真实过程视频、可核顺序和权利 | 只展示结果却声称过程 |
| `CP12` | 录屏路径动作首帧 | 软件教程、后台路径、工具操作 | 当前版本录屏、设备/版本、验证路径和脱敏 | 伪 UI 或过期路径 |
| `CP13` | 真人口播 / 现场判断首帧 | 解释、判断、现场观察 | 授权真人、表达来源、经历范围和权利 | 用脸和专家腔替代证据 |

详细 job、carrier、素材门、版式合同、反例与 evidence refs 以 JSON 资产为准；不要从这张表靠语感补全。

## 3. 用选择器，不凭记忆挑模板

```bash
python scripts/select_cover_pattern.py \
  --job feed_stop \
  --carrier text_card \
  --materials truthful_serious_premise \
  --visual-evidence-role none \
  --json
```

文字型任务在素材门通过时优先返回 `CP01`。如果画面本身是第一份证据：

```bash
python scripts/select_cover_pattern.py \
  --job decision_support \
  --carrier comparison_warning \
  --materials owned_or_authorized_before_after \
  --visual-evidence-role primary \
  --json
```

这时返回 `CP05`。强制指定 `--pattern-id CP01` 会得到 `contraindicated`，而不是把真实结果图藏到内页。

状态含义：

| status | 含义 | 下一步 |
| --- | --- | --- |
| `matched` | exact job/carrier、素材门和反例门均通过 | 继续选视觉方向卡与 style binding |
| `needs_materials` | 载体正确，但缺真实素材 | 补素材或换任务，不让模型补证据 |
| `contraindicated` | 该模式与当前证据角色冲突 | 采用返回的证据型载体 |
| `needs_research` | 没有 exact job/carrier 模式 | 保存 gap；不要类比拼装 |
| `invalid_contract` | 资产损坏或 schema 漂移 | 停止生产并修复资产 |

选择器只决定 `carrier/task-fit`，不决定最终颜色、字形、裁切或发布资格。

## 4. 三种优先字卡怎样生成

文字必须由确定性排版渲染。图像模型可生成背景素材，但不能承担最终中文拼写。

输入 JSON：

```json
{
  "variant": "black_accent_card",
  "headline": "说一个暴论：\n真正好用的封面，\n先让人看懂",
  "accent_terms": ["暴论", "看懂"],
  "meta": "NATIVE COVER · 07/18",
  "output_path": "cover.png"
}
```

运行：

```bash
python scripts/render_text_card_cover.py --input input.json
```

可用变体：

| variant | 视觉语法 | 约束 |
| --- | --- | --- |
| `black_accent_card` | 外圈强调色、黑色大圆角卡、白字 + 单一强调色 | 适合强命题；不要加入图标矩阵和多模块 |
| `paper_meme_card` | 暖纸张、轻网格、描边大字、可选一个授权物件/梗图 | 问题必须脱离梗图仍可读 |
| `highlight_note_card` | 高能浅底、自然换行、局部词块高亮 | 高亮最多两处，不把每个词做贴纸 |

共同硬门：1080×1440 RGB PNG；最多两处语义强调；显式换行优先；超出安全区直接 `text_overflow`，不自动缩成 PPT 密度；可选贴图必须同时提供 `sticker_rights_status=owned|authorized`。输出固定是 `prototype_only / not_performance_evidence`。

仓库示例：[`text-card-demo.png`](../assets/cover-render-examples/text-card-demo.png)。它证明渲染器能稳定输出中文与版式，不证明该文案会获得流量。

## 5. 模式、方向卡、风格规则的分工

```text
CP cover pattern
  解决：文字还是画面先工作，首屏用哪种载体
        ↓
VDC visual direction
  解决：真实素材按什么 attention/proof order 到达
        ↓
published style binding
  解决：当前账号 exact category/job/carrier 的颜色、字形、裁切、密度和标注语法
        ↓
renderer / real asset compositor
  解决：精确生成文件
```

没有 published binding 时，CP/VDC 和字卡渲染器最多给一个 `prototype_only`。不得把 CP01 的薄荷色、CP02 的纸张或 CP03 的荧光块改名为“平台喜欢的配色”。

## 6. 两层视觉 QA

先看信息流缩略图，再看全图：

- 缩略图：两秒能否读懂主命题；第一证据是否可见；焦点是否只有一个。
- 全图：中文是否正确；有无孤字、溢出、遮挡；强调是否真的对应语义；素材权利与真实性是否闭合。
- Anti-PPT：有没有圆角卡 + 三条 bullet + 图标矩阵的无证据重复；有没有为了“精致”抹掉生活材质。
- 防过拟合：把同一视觉结构换成低表现截图仍成立时，它只能是系列常量或任务适配，不能写成流量密码。

来源与限制见 [`2026-07-18-native-cover-patterns.md`](../../docs/research/2026-07-18-native-cover-patterns.md)。
