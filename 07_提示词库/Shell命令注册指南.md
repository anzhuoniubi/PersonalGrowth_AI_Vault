# Shell 命令注册指南

> 让 Obsidian 按钮能执行终端命令 · 依赖：Shell Commands 插件

---

## 一、注册方法

> ⚠️ 命令已通过 `data.json` 预配置，**无需手动注册**。重启Obsidian后 `Cmd+P` 输入 `cc:` 即可看到全部命令。
>
> 如需修改，进入 **设置 → Shell Commands**，找到对应命令编辑。

---

## 二、命令清单（逐条注册）

### cc:git-push — Git提交推送

```
Alias: cc:git-push
Shell command:
  cd "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault" && git add -A && git commit -m "auto: $(date +%Y-%m-%d_%H:%M)" && git push origin main
Platform: macOS (default)
Confirm before execution: ✅
Output channel: Notification
```

### cc:import-data — 导入最新Excel数据

```
Alias: cc:import-data
Shell command:
  python3 -c "
import openpyxl, glob, os
files = sorted(glob.glob('/Users/mac/Downloads/笔记列表明细表*.xlsx'), key=os.path.getmtime, reverse=True)
if files:
    wb = openpyxl.load_workbook(files[0], data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    for i, r in enumerate(rows[2:8] if len(rows) > 2 else []):
        print(f'{r[0]} | 曝光:{r[3]} | 观看:{r[4]} | CTR:{r[5]} | 互动:{int(r[6] or 0)+int(r[7] or 0)+int(r[8] or 0)+int(r[10] or 0)}')
    print(f'Done: {os.path.basename(files[0])}')
else:
    print('No data file found')
"
Platform: macOS (default)
Output channel: Modal
```

### cc:mcp-health — MCP健康检查

```
Alias: cc:mcp-health
Shell command:
  echo "=== MCP Health Check ===" &&
  echo "Sequential Thinking: $(node -e 'require(\"/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/node_modules/@modelcontextprotocol/server-sequential-thinking/dist/index.js\")' 2>&1 | head -1 || echo 'ERROR')" &&
  echo "Playwright: $(npx playwright --version 2>&1)" &&
  echo "Filesystem: $(node -e 'require(\"/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js\")' 2>&1 | head -1 || echo 'ERROR')" &&
  echo "GitHub: $(gh auth status 2>&1 | head -1)" &&
  echo "Memory: $(ls -la /Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/memory/mcp_knowledge_graph.json 2>&1 || echo 'Not yet created')" &&
  echo "=== Check Complete ==="
Platform: macOS (default)
Output channel: Modal
```

### cc:render-cover — 渲染小红书封面

```
Alias: cc:render-cover
Shell command:
  cd "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/skills/redbook-auto" && python3 scripts/render_xhs_v2.py
Platform: macOS (default)
Output channel: Notification
```

### cc:content-production — 启动内容生产

```
Alias: cc:content-production
Shell command:
  osascript -e 'display notification "内容生产流程已启动" with title "半醒之间 OS"'
Platform: macOS (default)
Output channel: Notification
```

*（此命令作为触发器，实际创作由 Claude Code 完成）*

### cc:weekly-review — 启动周度复盘

```
Alias: cc:weekly-review
Shell command:
  osascript -e 'display notification "周度复盘已启动，请切换到 Claude Code" with title "半醒之间 OS"'
Platform: macOS (default)
Output channel: Notification
```

### cc:user-research — 启动用户研究

```
Alias: cc:user-research
Shell command:
  osascript -e 'display notification "用户研究已启动" with title "半醒之间 OS"'
Platform: macOS (default)
Output channel: Notification
```

### cc:viral-analysis — 启动爆款拆解

```
Alias: cc:viral-analysis
Shell command:
  osascript -e 'display notification "爆款拆解已启动" with title "半醒之间 OS"'
Platform: macOS (default)
Output channel: Notification
```

### cc:mcp-restart-memory — 重启Memory

```
Alias: cc:mcp-restart-memory
Shell command:
  rm -f "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/memory/mcp_knowledge_graph.json" && echo "Memory graph cleared. Restart Claude Code to reinitialize." && osascript -e 'display notification "Memory已重置" with title "MCP控制台"'
Platform: macOS (default)
Output channel: Notification
```

### cc:mcp-clean-memory — 清理Memory图谱

```
Alias: cc:mcp-clean-memory
Shell command:
  rm -f "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault/memory/mcp_knowledge_graph.json" && echo "Cleaned." && osascript -e 'display notification "Memory图谱已清理" with title "MCP控制台"'
Platform: macOS (default)
Output channel: Notification
```

### cc:mcp-playwright-test — 浏览器截图测试

```
Alias: cc:mcp-playwright-test
Shell command:
  cd "/Users/mac/Documents/Obsidian/PersonalGrowth_AI_Vault" && node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://www.xiaohongshu.com');
  console.log('Title:', await page.title());
  await browser.close();
  console.log('Playwright test passed.');
})();
"
Platform: macOS (default)
Output channel: Modal
Confirm before execution: ✅
```

---

## 三、验证方法

注册完成后，点击 [[📊 运营驾驶舱]] 中的任意按钮，应看到：

- ✅ 通知弹出（notification类型）
- ✅ 弹窗显示结果（modal类型）
- ✅ 顶部状态栏短暂提示

---

## 四、排错

| 症状 | 解决 |
|------|------|
| 按钮点击无反应 | 检查Shell Commands插件是否启用；命令Alias是否与按钮中的完全一致 |
| `command not found` | 使用完整路径（如 `/usr/local/bin/python3`） |
| 权限不足 | `chmod +x` 或检查文件路径是否存在 |
| Playwright报错 | `npx playwright install chromium` |

---

*关联：[[07_提示词库/MCP控制台|MCP控制台]] · [[07_提示词库/MCP使用手册|MCP使用手册]] · [[📊 运营驾驶舱|运营驾驶舱]]*
