[English](README.md) | [繁體中文](README.zh.md)

# Maestro

一個 Claude Code 技能，智慧地將任務分配到多個 CLI 工具 — **Claude Code**、**Codex CLI** 和 **Gemini CLI** — 根據 CP 值選擇最佳代理和執行模式。

## 功能特色

Maestro 分析您的任務並自動選擇最佳協作模式：

| 模式 | 代理數 | 適用場景 |
|---|---|---|
| Solo | 1 | 簡單、明確、單一範圍的任務 |
| Pipeline | 2-5 順序執行 | 多階段工作（規劃、實作、審查） |
| Race | 2-3 平行執行 | 品質優先；比較多個 CLI 的輸出 |
| Swarm | 3+ 平行執行 | 可拆分為獨立子任務的大型任務 |
| Escalation | 1 逐步升級 | 預算優先；從便宜開始，品質不足再升級 |

**核心設計原則：** Solo 是預設模式，涵蓋約 70% 的任務。更複雜的模式僅在任務確實受益於多代理協作時才使用。

## 安裝

1. 將此倉庫 clone 到 Claude 技能目錄：

   ```bash
   git clone https://github.com/joneshong-skills/maestro.git ~/.claude/skills/maestro
   ```

2. 前置需求：
   - Python 3.10+
   - 至少安裝一個無頭 CLI 技能（claude-code-headless、codex-headless 或 gemini-cli-headless）
   - `model-mentor` 和 `team-tasks` 技能（用於路由和協調）

3. 當您提到協作、多代理任務、分配、競速 CLI，或使用觸發詞如「協作」、「分配任務」、「用三個 CLI」等時，技能會自動啟動。

## 使用方式

```bash
MAESTRO="python3 ~/.claude/skills/maestro/scripts/maestro.py"

# 自動分析並分配（最常用）
$MAESTRO run "修復 auth.ts 中的登入 bug" --cwd /path/to/project

# 明確指定模式
$MAESTRO run --pattern pipeline "建立使用者註冊功能" --cwd /path/to/project

# 預覽計畫（不執行）
$MAESTRO plan "重構整個付款模組"

# 查看狀態和報告
$MAESTRO status maestro-20260211-143022
$MAESTRO report maestro-20260211-143022
```

## 專案結構

```
maestro/
├── SKILL.md                        # 技能定義及協作邏輯
├── README.md                       # 英文說明
├── README.zh.md                    # 繁體中文說明（本檔案）
├── scripts/
│   └── maestro.py                  # 核心分配器和執行引擎
├── references/
│   ├── decision-tree.md            # 完整模式選擇決策樹
│   └── pattern-catalog.md          # 詳細模式定義和指南
└── examples/
    ├── solo-dispatch.sh            # Solo 模式端對端範例
    ├── pipeline-review.sh          # Pipeline 含規劃/實作/審查階段
    └── race-comparison.sh          # 3 個 CLI 競速安全審查
```

## 授權

MIT
