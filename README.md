# PaperAssistant

航空发动机领域文献自动检索、评分与管理工具。基于 OpenAlex / Semantic Scholar 学术 API，结合 Zotero 文献库去重和多维度评分，实现从检索到入库的完整工作流。

## 功能

- **双源检索** — 同时搜索 OpenAlex 和 Semantic Scholar，自动合并去重
- **智能查重** — 与 Zotero 文献库比对（DOI 精确匹配 + 标题模糊匹配），过滤已入库文献
- **多维度评分** — 相关性（关键词命中）、质量（引用次数）、新颖性、时效性四维加权评分
- **期刊过滤** — 支持 ISSN 精确过滤，聚焦目标期刊
- **周报生成** — 自动生成按优先级分类的 Markdown 周报
- **Claude Code 集成** — 通过 MCP 工具调用 Zotero / Obsidian / OpenAlex / Semantic Scholar，一键审阅入库

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

仅依赖 `pyyaml` 和 `requests`。

### 配置

编辑 `config/search_config.yaml`：

```yaml
topics:
  - name: "进气畸变"
    keywords:
      - "inlet distortion"
      - "total pressure distortion"
      - "circumferential distortion"
    years: "1960-2026"
    monitor: true

scoring:
  relevance_weight: 0.40
  quality_weight: 0.20
  novelty_weight: 0.25
  recency_weight: 0.15
  top_n_candidates: 10

openalex:
  email: "your-email@example.com"   # 用于 OpenAlex 礼貌池，提高速率
  api_key: ""                        # 可选，Premium API key
  max_results_per_query: 100

journals:
  - name: "ASME J. Turbomachinery"
    issn: "0889-504X"
  - name: "Chinese Journal of Aeronautics"
    issn: "1000-9361"
  # 更多期刊...
```

### 运行

**一次性检索：**

```bash
python scripts/search_openalex.py --config config/search_config.yaml --topic "进气畸变"
```

**完整流水线（去重 + 评分）：**

```bash
# 1. 搜索
python scripts/search_openalex.py --config config/search_config.yaml --topic "进气畸变"

# 2. 去重
python scripts/compare_library.py \
  --input output/search_进气畸变_<timestamp>.json \
  --library config/zotero_library.csv \
  --output output/filtered_进气畸变_<timestamp>.json

# 3. 评分
python scripts/score_papers.py \
  --input output/filtered_进气畸变_<timestamp>.json \
  --config config/search_config.yaml \
  --topic "进气畸变" \
  --output output/scored_进气畸变_<timestamp>.json
```

**自动周报：**

```bash
python scripts/monitor.py
```

输出：
- `output/weekly_report_<YYYY>-W<WW>.md` — 按优先级分类的周报
- `output/monitor_<课题>_<YYYY>-W<WW>.json` — 详细评分数据

## 项目结构

```
PaperAssistant/
├── config/
│   ├── search_config.yaml      # 课题、关键词、评分权重配置
│   └── zotero_library.csv      # Zotero 文献库导出（去重用）
├── scripts/
│   ├── search_openalex.py      # OpenAlex API 检索
│   ├── compare_library.py      # Zotero 文献库查重
│   ├── score_papers.py         # 多维度评分排序
│   └── monitor.py              # 周报自动编排器
├── output/                      # 检索结果（自动生成）
├── tests/                       # 单元测试
├── docs/                        # 设计文档和使用指南
└── requirements.txt
```

## 评分体系

| 维度 | 权重 | 计算方式 |
|------|------|----------|
| 相关性 (relevance) | 0.40 | 标题+摘要中关键词命中率 |
| 质量 (quality) | 0.20 | 引用次数对数缩放 |
| 新颖性 (novelty) | 0.25 | 默认 50（需人工调整） |
| 时效性 (recency) | 0.15 | 按发表年份衰减 |

综合分 = Σ(维度分 × 权重)，按综合分降序排列取 Top N。

## Claude Code 集成

本项目可作为 [Claude Code Skill](https://docs.anthropic.com/en/docs/claude-code/skills) 使用，通过 MCP 工具实现全自动化：

| MCP 服务 | 用途 |
|----------|------|
| `openalex-mcp-server` | OpenAlex 学术搜索 |
| `semanticscholar` | Semantic Scholar 学术搜索 |
| `zotero-mcp` | Zotero 文献库管理 |
| `obsidian` | Obsidian 笔记创建 |

Skill 文件位于 `~/.claude/skills/PaperAssistant/skill.md`，支持：
- `/PaperAssistant` 一键启动交互式检索
- `/PaperAssistant monitor` 运行周报监控
- 逐篇审阅，一键保存到 Zotero + 创建 Obsidian 笔记

## 测试

```bash
python -m pytest tests/ -v
```

## 依赖

- Python 3.10+
- pyyaml >= 6.0
- requests >= 2.28

## License

MIT
