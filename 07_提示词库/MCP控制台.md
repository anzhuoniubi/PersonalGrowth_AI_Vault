# 🖥️ MCP 控制台

> 5个MCP Server状态面板 · `= date(today).format("YYYY-MM-DD HH:mm")`

---

## 🚥 服务状态

| 服务 | 状态 | 端口 | 最后心跳 |
|------|:----:|:----:|:--------:|
| Sequential Thinking | 🟢 运行中 | stdio | `= date(today)` |
| Playwright | 🟢 运行中 | stdio | `= date(today)` |
| Filesystem | 🟢 运行中 | stdio | `= date(today)` |
| GitHub | 🟢 运行中 | stdio | `= date(today)` |
| Memory | 🟢 运行中 | stdio | `= date(today)` |

---

## 🔧 快捷操作

```button
name 🩺 MCP健康检查
type command
action Shell commands: Execute: cc:mcp-health
color blue
```
```button
name 🔄 重启Memory服务
type command
action Shell commands: Execute: cc:mcp-restart-memory
color orange
```
```button
name 🧹 清理Memory图谱
type command
action Shell commands: Execute: cc:mcp-clean-memory
color red
```
```button
name 🤖 浏览器截图测试
type command
action Shell commands: Execute: cc:mcp-playwright-test
color purple
```

---

## 📋 已注册Shell命令

| 命令ID | 命令 | 关联Agent |
|--------|------|:---------:|
| `cc:content-production` | 启动内容生产流程 | 内容Agent |
| `cc:weekly-review` | 启动周度复盘 | 复盘Agent |
| `cc:user-research` | 启动用户研究 | 研究Agent |
| `cc:viral-analysis` | 启动爆款拆解 | 爆款分析Agent |
| `cc:render-cover` | 渲染小红书封面 | 视觉Agent |
| `cc:publish-xhs` | 发布小红书笔记 | 内容Agent |
| `cc:git-push` | 提交并推送GitHub | — |
| `cc:import-data` | 导入Excel数据 | 复盘Agent |
| `cc:mcp-health` | MCP健康检查 | — |
| `cc:mcp-restart-memory` | 重启Memory服务 | — |
| `cc:mcp-clean-memory` | 清理Memory图谱 | — |
| `cc:mcp-playwright-test` | 浏览器截图测试 | — |

---

## 🗄️ Memory图谱信息

```dataview
TABLE 
  file.size AS "大小",
  dateformat(file.mtime, "MM-dd HH:mm") AS "最后修改"
FROM "memory"
WHERE file.name = "mcp_knowledge_graph"
```

---

## 📦 依赖版本

| 包 | 版本 |
|----|:----:|
| `@modelcontextprotocol/server-sequential-thinking` | 2026.7.4 |
| `@playwright/mcp` | 0.0.78 |
| `@modelcontextprotocol/server-filesystem` | 2026.7.10 |
| `@modelcontextprotocol/server-github` | 2025.4.8 |
| `@modelcontextprotocol/server-memory` | 2026.7.4 |

---

*关联：[[07_提示词库/MCP使用手册|MCP使用手册]] · [[07_提示词库/Shell命令注册指南|Shell命令注册指南]] · [[📊 运营驾驶舱|运营驾驶舱]]*
