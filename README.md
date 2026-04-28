# kicad-jlc-tools

在 KiCad 原理图中管理嘉立创/LCSC 元器件编号——基于本地 LCSC 数据库自动匹配元器件、编辑属性、导出 JLCPCB BOM。

Manage JLC/LCSC part numbers in KiCad schematics — auto-match components against the LCSC database, edit properties, and export JLCPCB-ready BOM.

## 功能特性 | Features

- **自动匹配** — 基于本地 FTS5 数据库将原理图元器件匹配到 LCSC 器件
- **封装回写** — 匹配后自动将 JLC 封装写回 KiCad 原理图，GUI 中支持手动修改和恢复封装
- **读写保护** — 读写 KiCad `.kicad_sch` 文件，保持原始格式不变
- **BOM 导出** — 导出 JLCPCB 格式 CSV（分组/平铺）和完整明细格式
- **导入编号** — 从 CSV 或 JSON 文件导入 LCSC 编号
- **命令行 + 图形界面** — `kicad-jlc` 用于脚本，`kicad-jlc-gui` 用于交互编辑
- **零运行依赖** — 纯 Python 标准库，无需 pip 安装额外包

## 安装 | Installation

从 GitHub 直接安装：

```bash
pip install git+https://github.com/tomdog2016/kicad-jlc-tools.git
```

或者克隆后本地安装：

```bash
git clone https://github.com/tomdog2016/kicad-jlc-tools.git
cd kicad-jlc-tools
pip install .
```

开发模式：

```bash
pip install -e ".[dev]"
```

## 嘉立创元器件数据库 | LCSC Component Database

首次使用前需要下载嘉立创元器件数据库（约 700 MB，FTS5 SQLite 格式）：

```bash
kicad-jlc db download
```

数据库包含 LCSC 全量元器件目录，用于自动匹配原理图中的元器件到嘉立创编号。数据库会保存在用户目录下，后续可使用 `kicad-jlc db update` 更新。

Before first use, download the LCSC component database (~700 MB FTS5 SQLite):

```bash
kicad-jlc db download
```

The database contains the full LCSC component catalog for auto-matching schematic components to JLC part numbers.

## 快速开始 | Quick Start

### 命令行 | CLI

```bash
# 下载嘉立创元器件数据库 (~700 MB)
kicad-jlc db download

# 列出原理图中的所有元器件
kicad-jlc load path/to/board.kicad_sch

# 自动匹配元器件并写回 LCSC 编号
kicad-jlc match path/to/board.kicad_sch --apply

# 手动设置某个元器件的 LCSC 编号和封装
kicad-jlc apply path/to/board.kicad_sch --ref R1 --lcsc C25744
kicad-jlc apply path/to/board.kicad_sch --ref R1 --footprint "Resistor_SMD:R_0402_1005Metric"

# 导出 JLCPCB BOM CSV
kicad-jlc export path/to/board.kicad_sch -o bom.csv

# 导出完整 BOM（含制造商、库存、状态等）
kicad-jlc export path/to/board.kicad_sch --full
```

### 图形界面 | GUI

```bash
kicad-jlc-gui
```

双击任意元器件可搜索 LCSC 数据库，或使用工具栏批量操作：

- **打开原理图** — 加载 `.kicad_sch` 文件
- **全部自动匹配** — 批量匹配未匹配的元器件
- **修改封装** — 手动修改元器件封装并回写到原理图，支持一键恢复原始封装
- **导出 BOM** — 导出 JLCPCB 格式 CSV
- **导入编号** — 从 CSV/JSON 导入 LCSC 编号
- **下载数据库** — 获取嘉立创元器件数据库

## 工作原理 | How It Works

```
.kicad_sch  ──解析──►  元器件列表
                           │
                    ┌──────▼──────┐
                    │ FTS5 搜索   │ ◄── parts-fts5.db (LCSC 器件库)
                    └──────┬──────┘
                           │
                  匹配的 LCSC 编号
                           │
              ┌────────────▼────────────┐
              │   定位文本替换           │ ──►  .kicad_sch (保持原格式)
              └────────────────────────┘
```

1. **解析** — S-expression 词法分析器 + 递归下降解析器，将 `.kicad_sch` 解析为 AST
2. **匹配** — 多轮 FTS5 搜索（值+封装 → 值 → 分词），按库存量排序
3. **写入** — 行级精确文本替换，原地编辑属性（LCSC 编号、封装），保持 KiCad 格式和缩进不变

## 项目结构 | Project Structure

```
src/kicad_jlc_tools/
├── __init__.py        # 公开 API
├── models.py          # Component, MatchResult, MatchStatus 数据类
├── parser.py          # S-expression 词法分析和解析器
├── schematic.py       # KiCad .kicad_sch 读写器
├── database.py        # 嘉立创/LCSC FTS5 数据库（搜索、下载）
├── matcher.py         # 自动匹配引擎
├── bom.py             # BOM CSV 导出和导入
├── exceptions.py      # 自定义异常
├── cli/main.py        # CLI 入口 (kicad-jlc)
└── gui/app.py         # Tkinter GUI 入口 (kicad-jlc-gui)
```

## 系统要求 | Requirements

- Python 3.10+
- 无运行时依赖

开发依赖：`pytest`、`pytest-cov`、`ruff`

## 许可证 | License

MIT
