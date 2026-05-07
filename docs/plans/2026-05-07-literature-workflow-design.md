# 个人文献检索、收纳、分析工作流 — 设计文档

**日期**: 2026-05-07
**状态**: 已确认

## 目标

解决 Zotero 能管理文献但无法主动发现新文献的痛点，构建覆盖 "搜索 → 筛选 → 审批 → 入库 → 笔记" 的完整工作流。

**研究领域**: 航空发动机
**数据源**: OpenAlex API

---

## 架构：混合模式（Claude Skill + Python 脚本）

```
┌─────────────────────────────────┐
│         用户交互层                │
│   Claude Skill (CLAUDE.md)       │
│   - 接受自然语言指令              │
│   - 展示候选论文/推荐理由          │
│   - 获取入库审批                  │
│   - MCP 写入 Zotero + Obsidian    │
└──────────┬──────────────────────┘
           │ 调用
┌──────────▼──────────────────────┐
│      Python 脚本层 (可复用)       │
│   - search_openalex.py           │
│   - compare_library.py           │
│   - score_papers.py              │
│   - monitor.py                   │
└─────────────────────────────────┘
```

---

## 项目结构

```
PaperAssistant/
├── CLAUDE.md                      # Skill 指令（工作流定义）
├── scripts/
│   ├── search_openalex.py         # OpenAlex API 查询
│   ├── compare_library.py         # Zotero 库对比去重
│   ├── score_papers.py            # 多维度打分排序
│   └── monitor.py                 # 每周定时任务入口
├── config/
│   └── search_config.yaml         # 搜索策略、评分权重、课题配置
└── output/                        # 临时搜索结果 & 周报
```

## 组件职责

| 组件 | 职责 |
|------|------|
| CLAUDE.md | Skill 入口，定义交互指令，编排脚本调用，驱动 MCP 入库和笔记生成 |
| search_openalex.py | 接收关键词/筛选条件，调 OpenAlex API，返回结构化 JSON |
| compare_library.py | 读取 Zotero 已有库，按 DOI/标题去重，标记新颖度 |
| score_papers.py | 四维打分：主题相关度、来源质量、新颖性、时效性 |
| monitor.py | 每周定时入口，串联搜索→对比→打分，生成 markdown 报告 |
| search_config.yaml | 持久化搜索策略：各课题关键词、评分权重、监控开关 |

---

## 数据流

### 交互模式

```
用户 → Claude: "搜索涡轮冷却 2024-2026 新论文"
  → search_openalex.py → OpenAlex API → 原始结果 JSON
  → compare_library.py → Zotero 库对比 → 去重 + 新颖度标记
  → score_papers.py → 四维打分 → Top-N 候选
  → Claude 逐篇展示候选：标题、摘要、分数、推荐理由
  → 用户勾选入库
  → Zotero MCP 创建条目
  → Obsidian MCP 生成文献笔记 + 更新周总结
```

### 监控模式（每周）

```
Windows 任务计划程序（每周定时）
  → python monitor.py
    → 读取 config/search_config.yaml 中 monitor:true 的课题
    → search_openalex.py → OpenAlex
    → compare_library.py → Zotero 对比
    → score_papers.py → 打分排序
    → 生成 output/weekly_report_YYYY-Www.md
  → 下次打开 Claude Code 时读取报告
  → 展示新发现 → 审批 → 入库 + 笔记
```

---

## 评分模型

| 维度 | 权重 | 计算方式 |
|------|------|----------|
| 主题相关度 | 40% | 标题+摘要与关键词/已有文献主题的语义匹配度 |
| 来源质量 | 20% | OpenAlex 引用数 + 期刊等级 |
| 新颖性 | 25% | 与 Zotero 已有库的差异度（避免高度重复） |
| 时效性 | 15% | 发表时间衰减曲线 |

- Top-N 候选数默认 10，可在配置中调整
- 权重可在 search_config.yaml 中按课题覆盖

---

## Obsidian 产出

### 目录结构
```
Vault/
├── 01 每周总结/
│   └── 2026-W19.md              # 文献监控作为周总结的一个板块
│
└── 02 Reading notes/
    ├── 涡轮冷却/
    │   ├── Film Cooling ... .md
    │   └── Heat Transfer ... .md
    └── 航空发动机燃烧/
        └── ...
```

### 周总结（含文献监控板块）
- 监控概览表格
- 阅读清单（高/中/低优先级，wikilink 链接到文献笔记）
- 值得关注标记（引用上升等）

### 文献笔记（按课题分目录）
- frontmatter: tags, authors, year, doi, zotero_key, score, status, topic
- 基本信息、摘要、入库理由、阅读 checklist
- 通过 `来源周报: [[2026-W19]]` 反向链接

---

## 定时机制

Windows 任务计划程序 → `python monitor.py` → 生成报告到 output/
用户下次打开 Claude Code → 读取报告 → 审批入库

不依赖 Claude 在线，筛选阶段由 Python 规则完成。

---

## 约束

- 文献入库需经用户明确审批，不自动添加
- 搜索量控制在每课题每轮 ≤50 篇（尊重 OpenAlex 速率限制）
- 已入库文献不再重复推荐
