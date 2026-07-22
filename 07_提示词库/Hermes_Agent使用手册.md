# Hermes Agent 使用手册

> 集成到 Personal Growth AI Self Media OS 的自我进化AI Agent
> 版本：v0.18.2 | 模型：DeepSeek | 进化成本：~$0.3-1.0/次

---

## 一、快速开始

### 启动
```bash
source ~/.zshrc    # 刷新环境变量（新终端可跳过）
hermes              # 启动对话
```

### 退出
```
按 Ctrl+C 或 输入 /exit
```

### 验证连接
```bash
hermes --version
# 输出：Hermes Agent v0.18.2 ...
```

---

## 二、核心概念

### Skill（技能）
Hermes 的技能系统和你 vault 里的 `skills/` 目录一一对应。每个 Skill 是一个 `SKILL.md` 文件，定义了 Agent 完成特定任务的指令。

你的23个本地Skill已全部注册：
```
skills/content/   → 标题生成、小红书文案写作、金句生成
skills/visual/    → 封面设计、AI绘图提示词
skills/data/      → 数据分析、爆款拆解、A_B测试
skills/research/  → 评论分析、情绪分析、用户痛点挖掘、搜索关键词分析、用户需求建模
skills/strategy/  → 个人品牌定位、用户画像分析、赛道分析
skills/growth/    → 互动运营、增长策略
skills/monetization/ → 产品设计、私域运营、课程设计
skills/video/     → 视频脚本创作
```

### 进化循环
Hermes 最核心的能力——**Skill 自我进化**：

```
你执行任务 → Hermes记录执行轨迹 → 分析哪里可以改进
  → GEPA引擎生成改进版Skill → 你审批 → 下次自动用新版本
```

---

## 三、常用命令

### 终端命令

| 命令 | 用途 |
|------|------|
| `hermes` | 启动对话 |
| `hermes -c` | 恢复上次会话 |
| `hermes setup` | 重新配置（模型/API密钥） |
| `hermes model` | 切换模型 |
| `hermes config list` | 查看配置 |
| `hermes config edit` | 编辑配置文件 |
| `hermes doctor` | 系统诊断 |
| `hermes update` | 更新到最新版本 |
| `hermes skills list` | 查看所有已注册技能 |
| `hermes skills browse` | 浏览技能市场 |
| `hermes skills install <name>` | 安装第三方技能 |

### 对话内命令

在 `hermes` 对话界面中输入 `/` 开头触发：

| 命令 | 用途 | 使用频率 |
|------|------|---------|
| `/help` | 查看所有命令 | 需要时 |
| `/skills` | 查看/管理技能 | ⭐ 常用 |
| `/learn` | 从当前工作流创建技能 | ⭐⭐⭐ 最核心 |
| `/model` | 切换模型 | 需要时 |
| `/save` | 保存当前对话 | ⭐ 推荐 |
| `/journey` | 查看记忆与技能成长时间线 | 每周 |
| `/tools` | 查看当前可用工具 | 需要时 |
| `/goal` | 设定完成契约目标 | 进阶 |

---

## 四、日常使用场景

### 场景1：创作小红书内容
```
hermes
进入对话 → "帮我写一篇关于普通人在AI时代自我觉察的内容，
调用标题生成Skill和文案写作Skill"
```

Hermes 会自动读取你注册的 Skill 文件，按其中定义的框架执行。

### 场景2：让Hermes从工作流中学习（/learn）
这是最有价值的功能。当你完成一个复杂任务后：

```
你在对话中完成了5步操作 →
输入 /learn →
Hermes自动将这次工作流提炼为一个可复用的Skill文件 →
存入 ~/.hermes/skills/ 目录 →
下次同类任务直接调用
```

**触发条件**：连续5次以上工具调用后，Hermes会自动提示是否创建Skill。

### 场景3：查看已注册的Skill
```bash
hermes skills list
```
```
│ 标题生成         │ local │ enabled │
│ 小红书文案写作   │ local │ enabled │
│ 封面设计         │ local │ enabled │
│ ... 共23个本地Skill
```

### 场景4：查看Hermes学到了什么
```
/journey
```
展示记忆与技能的成长时间线，可以看到Hermes从每次任务中积累的经验。

---

## 五、Skill 自我进化（GEPA）

### 进化流程
```
准备进化 → 运行GEPA → 生成变体 → 约束检查 → 你审批 → 入库
```

### 成本
用 DeepSeek 每次进化运行约 **$0.3-1.0**，需要约30万-70万 token 的API调用。

### 推荐进化频率

| Skill | 进化频率 | 月成本 |
|------|---------|--------|
| 标题生成 | 每月1次（根据CTR数据） | ~$0.5 |
| 小红书文案写作 | 每月1次（根据互动率数据） | ~$0.5 |
| 封面设计 | 每季度1次 | ~$0.3 |
| 其他Skill | 半年1次或不进化 | ~$0 |

**每月总成本约 $1-2**（用DeepSeek的情况下）。

### 进化前准备
确认已配置环境变量：
```bash
export HERMES_AGENT_REPO=~/.hermes/hermes-agent
```

### 运行进化
```bash
cd ~/.hermes/hermes-agent-self-evolution
python -m evolution.skills.evolve_skill \
    --skill 标题生成 \
    --iterations 10 \
    --eval-source synthetic
```

进化完成后会生成报告，最优版本以PR形式提交，你审批后合并。

---

## 六、集成到你的系统

### 系统架构图
```
你（Creator）
  ↓ 指令
CEO Agent（本Claude会话）
  ↓ 调度
┌─────────────────────────────────────┐
│  Hermes Agent (v0.18.2)             │
│  ├─ 23个本地Skill ← 你的vault skills │
│  ├─ DeepSeek 模型                   │
│  ├─ /learn 技能自创建               │
│  └─ GEPA 技能自进化                 │
└─────────────────────────────────────┘
  ↓
你的Obsidian Vault
  ├─ 05_内容生产库/  产出物
  ├─ 03_选题库/      选题
  └─ skills/         Skill进化后自动更新
```

### 信息流向
```
内容创作流程：
Creator → Claude（本系统）→ hermes（执行/学习）→ 产出物 → vault

Skill进化流程：
数据分析发现Skill需要优化 → hermes GEPA进化 → 新版本Skill
→ 你审批 → 下次创作自动用新版
```

### 你的23个Skill在Hermes中的位置
```bash
ls ~/.hermes/skills/
# 每个子目录下有一个 SKILL.md 文件
```

如果要更新某个Skill，直接编辑 vault 里的 `skills/xxx.md`，然后同步到 Hermes：
```bash
cp /Users/mac/.../skills/content/标题生成.md \
   ~/.hermes/skills/标题生成/SKILL.md
```

---

## 七、注意事项

### ✅ 推荐用法
- 日常用 `hermes` 对话界面做内容创作，让它调用你的Skill
- 完成复杂任务后用 `/learn` 让Hermes记住工作流
- 每月运行1次GEPA进化，优化核心Skill

### ❌ 注意
- `/learn` 的计数器不跨会话持久化，需要在同一会话内积累复杂任务
- subagent 的 tool call 不计入主 agent 计数
- Skill 写入默认开启审批（`write_approval: true`），所有变更需要你确认
- 第一次运行可能提示配置迁移，按提示执行即可

### 故障排除

| 问题 | 解决 |
|------|------|
| `hermes: command not found` | 执行 `source ~/.zshrc` 或重新打开终端 |
| 启动后无反应 | 可能是网络问题，检查DeepSeek API连通性 |
| 技能未加载 | 执行 `hermes skills list` 检查状态 |
| DeepSeek连接失败 | 检查API Key是否过期，运行 `hermes doctor` 诊断 |

---

*创建日期：2026-07-18*
*适用版本：Hermes Agent v0.18.2 + DeepSeek*
