# Board — 个人侦探线索板

基于 JSON 的个人任务/线索追踪系统，用侦探办案的隐喻管理生活、学习和项目。

## 数据模型

```
领域 (Domain) → 案件 (Case) → 线索 (Clue) / 任务 (Task)
```

- **领域**：生活分类（学校、编程、小说、哲学等）
- **案件**：领域内的具体问题或项目，有**重要度**（priority）和**紧急度**（urgency）两个维度
- **线索**：案件相关的证据/信息，带置信度（高/中/低）
- **任务**：可执行的行动项，带状态（待办→进行中→完成/阻塞）

## 快速开始

```bash
# 初始化
board init

# 查看总览
board show
board show --format table     # 任务列表视图

# 添加领域
board add-domain school "学校" --emoji 🏫

# 添加案件（注意：有 priority 和 urgency 两个维度）
board add-case school "与班主任的冲突" --priority high --urgency critical

# 添加线索
board add-clue school-001 "今天当众点名批评" --confidence high

# 添加任务
board add-task school-001 "找年级主任谈话" --priority high

# 更新案件/任务
board update-case school-001 --urgency medium --situation "情况有所缓和"
board update-task task-001 --status doing

# 快捷改状态
board move-task task-001 done

# 删除
board remove-clue clue-001
board remove-task task-001
board remove-case school-001

# 关联 Obsidian 笔记
board link-case school-001 "Concepts/学校权力结构分析"

# 渲染输出（生成可跨设备查看的产物）
board render --format md --output content/board.md
board render --format html --output content/board.html
```

## 命令清单

| 命令 | 说明 |
|------|------|
| `init [--force]` | 初始化 board-state.json |
| `show [--format table\|summary]` | 总览 |
| `add-domain <id> <name>` | 添加领域 |
| `add-case <domain> <title>` | 添加案件 |
| `update-case <case-id>` | 更新案件字段 |
| `add-clue <case> <text>` | 添加线索 |
| `add-task <case> <text>` | 添加任务 |
| `update-task <task-id>` | 更新任务字段 |
| `move-task <task-id> <status>` | 快捷改任务状态 |
| `remove-domain <id>` | 删除领域（级联） |
| `remove-case <id>` | 删除案件（级联） |
| `remove-clue <id>` | 删除线索 |
| `remove-task <id>` | 删除任务 |
| `link-case <case-id> <path>` | 关联 Obsidian 笔记 |
| `set-situation <text>` | 设置全局处境 |
| `render [--format md\|html]` | 渲染输出 |

## 案件双维度

每个案件有两个独立维度：

| 字段 | 含义 | 可选值 |
|------|------|--------|
| `priority` | 重要度 | critical / high / medium / low |
| `urgency` | 紧急度 | critical / high / medium / low |

类似艾森豪威尔矩阵：重要且紧急的优先处理，重要不紧急的持续跟进，紧急不重要的可以委托或快速完成。

## 文件结构

```
tools/board/
├── state.py          # 数据模型、CRUD、持久化
├── cli.py            # CLI 命令解析
├── renderer.py       # Markdown + HTML 渲染引擎
└── html/
    └── template.html # HTML 模板（侦探软木板风格）
```

纯 Python 标准库，无第三方依赖。
