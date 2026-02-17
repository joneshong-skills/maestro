<h1 align="center">Maestro</h1>

<p align="center">
  <a href="README.md"><kbd>English</kbd></a>
  <a href="README.zh.md"><kbd><strong>繁體中文</strong></kbd></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/joneshong-skills/maestro/main/logo.png" alt="Maestro Logo" width="200"/>
</p>

<p align="center">
  <a href="https://github.com/joneshong-skills/maestro">
    <img alt="GitHub" src="https://img.shields.io/github/stars/joneshong-skills/maestro?style=social">
  </a>
  <a href="https://deepwiki.com/joneshong-skills/maestro">
    <img alt="DeepWiki" src="https://img.shields.io/badge/DeepWiki-docs-blue">
  </a>
  <a href="https://github.com/joneshong-skills/maestro/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg">
  </a>
</p>

<p align="center">
  <strong>Claude Code 多 CLI 協作指揮官</strong>
</p>

<p align="center">
  智慧地將任務路由到合適的 CLI 工具 -- Claude Code、Codex CLI 和 Gemini CLI --
  根據 CP 值選擇最佳代理和執行模式。
</p>

## 功能特色

- **五種協作模式** -- Solo、Pipeline、Race、Swarm 和 Escalation，匹配各種任務形態
- **智慧路由** -- 根據任務類別、複雜度和預算約束自動選擇 CLI
- **Foreman 整合** -- 對唯讀任務優先使用輕量級子代理，而非完整 CLI 進程
- **預算模式** -- 最小化成本、平衡品質/成本，或以明確預算控制最大化品質
- **流水線範本** -- 預配置的常見工作流程階段序列（建置、審查、重構等）
- **結構化報告** -- 基於 JSON 的專案追蹤，含狀態監控和最終報告

## 使用方式

觸發詞："協作代理"、"分配任務"、"多代理執行"、"用三個 CLI"、"Claude vs Codex vs Gemini 競速"

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

## 協作模式

| 模式 | 代理數 | 適用場景 |
|------|--------|---------|
| **Solo** | 1 | 簡單、明確、單一範圍的任務（可能透過 foreman 委派給子代理） |
| **Pipeline** | 2-5 順序執行 | 多階段工作（規劃、實作、審查） |
| **Race** | 2-3 平行執行 | 品質優先；比較多個 CLI 的輸出 |
| **Swarm** | 3+ 平行執行 | 可拆分為獨立子任務的大型任務 |
| **Escalation** | 1 逐步升級 | 預算優先；從便宜開始，品質不足再升級 |

**核心設計原則：** Solo 是預設模式，涵蓋約 70% 的任務。

## Foreman 整合

Maestro 整合 **foreman** 技能，對唯讀任務優先使用輕量級子代理：

```
Solo 派遣流程：
  任務 -> check_agent_match() -> 找到代理？ -> dispatch_via_agent()（快速、便宜）
                                -> 沒有代理？ -> dispatch_via_cli()（完整 CLI）
```

何時優先使用代理而非 CLI：
- 唯讀分析任務（不需要沙箱）
- 有匹配的代理且分數 >= 0.15
- 任務不需要跨 CLI 能力

## 工作流程

1. **分析** -- 按類別、複雜度和可拆分性分類任務
2. **選擇模式** -- 套用決策樹選擇 Solo/Pipeline/Race/Swarm/Escalation
3. **路由** -- 使用路由表和預算模式映射到最佳 CLI
4. **執行** -- 透過 `maestro.py` 派遣，平行模式使用背景執行
5. **審查** -- 生成結構化報告，含各階段結果

## 技能整合

| 技能 | 關係 |
|------|------|
| **foreman** | 流水線中唯讀任務的輕量級子代理派遣層 |
| **model-mentor** | 提供 CLI 路由智慧和模型比較數據 |
| **team-tasks** | 多代理專案管理的協調層 |
| **claude-code-headless** | Claude Code 的無頭執行包裝器 |
| **codex-cli-headless** | Codex CLI 的無頭執行包裝器 |
| **gemini-cli-headless** | Gemini CLI 的無頭執行包裝器 |

## 安裝方式

將此儲存庫克隆到你的 Claude 技能目錄：

```bash
git clone https://github.com/joneshong-skills/maestro.git ~/.claude/skills/maestro
```

前置需求：
- Python 3.10+
- 至少安裝一個無頭 CLI 技能（claude-code-headless、codex-headless 或 gemini-cli-headless）
- `model-mentor` 和 `team-tasks` 技能（用於路由和協調）

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

## 授權條款

MIT
