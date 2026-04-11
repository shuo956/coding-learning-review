# ⟳ leetrevive

> **Language / 语言：** [English](README.md) · 中文

基于终端、本地优先的 LeetCode 间隔重复复习助手。

`leetrevive` 将你做过的题目变成个人复习题库，每天根据遗忘曲线智能安排哪些题该复习——优先推送最弱的题和到期的题，帮助你在面试前真正掌握每一道题。

**无需账号，不抓取题目内容，无订阅费用。** 所有数据存储在本机的一个 SQLite 文件中。

```
$ leetrevive today

  今日复习 — 2024-06-15
 ┏━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
 ┃ # ┃ 编号 ┃ 题目                    ┃ 难度 ┃ 到期日      ┃ 原因           ┃
 ┡━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
 │ 1 │ 23   │ Merge K Sorted Lists    │ 困难 │ 已逾期 3 天 │ 已逾期         │
 │ 2 │ 1    │ Two Sum                 │ 简单 │ 今天        │ 今日到期       │
 │ 3 │ 300  │ Longest Increasing Sub  │ 中等 │ 5 天后      │ 巩固: dp       │
 └───┴──────┴─────────────────────────┴──────┴─────────────┴────────────────┘
```

---

## 功能亮点

| | |
|---|---|
| 📥 **自动填充题目信息** | `leetrevive add 146` — 题目名称、难度、标签全部自动填充（内置 3892 道题的元数据，无需联网） |
| 🧠 **间隔重复算法** | 类 SM-2 调度器；得分越高，复习间隔自动延长 |
| 💡 **一句话核心思路** | 每道题附带由 Claude AI 生成的算法要点（例：*"使用最小堆合并 k 个有序流，时间复杂度 O(n log k)"*） |
| 🌐 **网页界面** | `leetrevive serve` 启动浏览器面板：今日复习卡片 + 可排序题库 |
| 🔗 **双链接** | 每道题同时提供 **LeetCode.com** 和 **力扣 (leetcode.cn)** 链接 |
| 🈳 **双语支持** | 网页界面支持 EN / 中文 切换；页面设置自动保存 |
| 🗄️ **本地优先** | 单个 SQLite 文件；可通过 `LEETREVIVE_DB_PATH` 自定义路径 |

---

## 快速开始

### 第一步 — 安装

```bash
# 需要 Python ≥ 3.10
git clone https://github.com/shuo956/lc_helper.git
cd lc_helper/.claude/worktrees/competent-shaw

# 建议使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate          # Windows 用：.venv\Scripts\activate

pip install --upgrade pip
pip install -e ".[web]"            # 加上 [dev] 可以运行测试
```

### 第二步 — 初始化数据库

```bash
leetrevive init
# ✓ 数据库已初始化：~/.local/share/leetrevive/leet.db
```

### 第三步 — 添加题目

```bash
# 只需输入编号，其余信息自动填充
leetrevive add 1       # Two Sum（简单）
leetrevive add 146     # LRU Cache（中等）
leetrevive add 200     # Number of Islands（中等）
leetrevive add 23      # Merge k Sorted Lists（困难）

# 也可手动指定信息
leetrevive add 999 "自定义题目" --difficulty medium
```

### 第四步 — 查看今日复习

```bash
leetrevive today
```

按题目尝试作答后，记录本次结果：

```bash
leetrevive done 1 --score 2
leetrevive done 146 --score 3 --minutes 12 --note "哈希表 + 双向链表"
```

**评分说明：**

| 分数 | 含义 |
|-----:|------|
| 0 | 完全忘记，无从下手 |
| 1 | 部分记得，需要提示或未完成 |
| 2 | 基本会，稍有犹豫 |
| 3 | 非常熟练，流畅完成 |

### 第五步 — 启动网页界面

```bash
leetrevive serve
# → 自动在浏览器中打开 http://localhost:8080
```

---

## 命令行参考

| 命令 | 说明 |
|------|------|
| `leetrevive init` | 创建 / 升级本地 SQLite 数据库 |
| `leetrevive add <编号> [题目名]` | 添加题目（仅输入编号时自动填充信息） |
| `leetrevive today` | 显示今日 3 道安排复习的题目 |
| `leetrevive done <编号> --score N` | 记录一次复习 |
| `leetrevive review <编号>` | 查看题目详情和完整复习历史 |
| `leetrevive bank` | 列出题库中所有题目 |
| `leetrevive open <编号>` | 在浏览器中打开 LeetCode 链接 |
| `leetrevive stats` | 查看统计数据（连续天数、总量、难度分布） |
| `leetrevive serve [--port 端口号]` | 启动网页面板（默认端口 8080） |

### `add` 可选参数

```bash
leetrevive add <编号> [题目名]
  --difficulty  easy|medium|hard    # 覆盖自动检测的难度
  --pattern     TEXT                # 算法模式标签（例：two-pointers）
  --url         TEXT                # 自定义链接
  --source      TEXT                # 来源标记（默认："manual"）
```

### `done` 可选参数

```bash
leetrevive done <编号>
  --score    0|1|2|3   （必填）
  --minutes  INT       # 解题用时（分钟）
  --note     TEXT      # 自由文本笔记
  --mistake  TEXT      # 易错点 / 下次要注意的地方
```

---

## 网页界面详解

```bash
leetrevive serve              # 使用默认端口 8080
leetrevive serve --port 9000  # 自定义端口
```

### 📅 今日复习（Today）选项卡

点击 **⚡ 生成今日题目** 加载今天的 3 道题。

每张卡片显示：
- 题目编号、标题、难度标签、算法标签
- 💡 一句话核心思路（算法关键点）
- 本次被选中的原因（已逾期 / 今日到期 / 巩固练习）
- **LeetCode ↗** — 打开 leetcode.com
- **力扣 ↗** — 打开 leetcode.cn
- **完成** 按钮 → 展开内联评分面板（无需跳转页面）

提交评分后，卡片会显示该题的下次复习日期。

**评分面板字段：**
- 分数 0–3（点击选择）
- 解题用时（分钟，可选）
- 笔记（可选）
- 易错点（可选）

### 📚 我的题库（My Bank）选项卡

**添加题目：**
1. 在搜索框中输入题号（例 `146`）
2. 题目名称和难度会实时预览
3. 按 **回车** 或点击 **添加**

**题目列表：**
- 点击列标题可按该列排序（编号 / 题目 / 难度 / 下次复习 / 复习次数）
- 过滤框支持按题目名、标签、难度搜索
- 到期日颜色标注：🔴 已逾期 · 🟡 今天 · 灰色 = 未来日期
- 每行的 **完成** 按钮展开内联评分面板

**语言切换（EN | 中文）：** 右上角，偏好自动保存至 localStorage。

---

## 间隔重复算法

| 分数 | 下次复习间隔 |
|-----:|-------------|
| 0 | 1 天（重置） |
| 1 | 3 天 |
| 2 | 间隔 × 2.0（连续 5 次"基本会"后上限 30 天） |
| 3 | 间隔 × 2.5（连续 5 次"非常熟练"后上限 60 天） |

**每日选题逻辑**（按优先级从高到低）：

1. **已逾期** — 超过到期日的题目
2. **今日到期** — 计划今天复习的题目
3. **久未复习** — 添加 ≥ 14 天但从未做过的题目
4. **巩固练习** — 从得分较低的题目中随机选取

---

## 数据管道

### 重新获取 LeetCode 元数据

```bash
pip install requests
python scripts/fetch_meta.py
# → src/leetrevive/data/problems_meta.json  (~1.2 MB，3892 道题)
```

### 重新生成一句话核心思路

需要 Anthropic API Key：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic
python scripts/generate_insights.py           # 生成所有题目
python scripts/generate_insights.py --resume  # 从上次中断处继续
# → src/leetrevive/data/insights.json
```

---

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LEETREVIVE_DB_PATH` | `~/.local/share/leetrevive/leet.db` | 覆盖 SQLite 文件路径（测试时使用） |
| `ANTHROPIC_API_KEY` | — | 仅 `generate_insights.py` 脚本需要 |

---

## 开发与测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

测试通过 `LEETREVIVE_DB_PATH` 将所有数据库操作定向到临时文件，无需 Mock。

---

## 项目结构

```
src/leetrevive/
├── cli.py              Typer 命令入口
├── db.py               原生 sqlite3（无 ORM）
├── models.py           Problem / Review / DailyPick 数据类
├── scheduler.py        纯函数间隔重复调度逻辑
├── meta.py             内置元数据 + 思路加载器（lru_cache）
├── utils.py            Rich 辅助函数、格式化工具
├── commands/           每个子命令一个文件
│   ├── add.py
│   ├── done.py
│   ├── today.py
│   ├── review.py
│   ├── bank.py
│   ├── stats.py
│   ├── open_.py
│   └── serve.py
├── web/
│   ├── server.py       FastAPI 后端
│   └── static/
│       └── index.html  单页应用（原生 JS，无框架依赖）
└── data/
    ├── problems_meta.json   3892 道 LeetCode 题目元数据
    └── insights.json        每道题的一句话核心思路
```

---

## 许可证

MIT
