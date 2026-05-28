# Chrono Social Engine

時間驅動的情感狀態引擎 — 為 AI 驅動的社交系統提供即時情緒語意。

**chronos.social engine** 是一個模組化的 Python 引擎，專門處理「時間 → 情感狀態」的即時計算。它不是一個現成的聊天機器人，而是一個可嵌入任何 AI Agent 系統的 **背景引擎**（background engine），負責：

追蹤使用者的沉默時長與時間區間
計算情緒抑制程度（emotional inhibition）
攜帶跨 session 的情感殘留（emotional carryover）
自動偵測情緒是否已被解除（resolved event）
產出可供 LLM 參考的情境提示（temporal block）

專為多角色 AI 系統（Hermes Agent 後宮等）設計，支援的角色數量無上限。

---

## 核心模組

| 模組 | 功能 |
|------|------|
| `core.py` | `TemporalContext`、`EmotionalCarryover`、`PersonaConfig` 資料結構與計算邏輯 |
| `db.py` | SQLite 持久化，carryover 的讀寫與 upsert |
| `resolver.py` | 自動偵測使用者情緒是否已解除（keyword + 情境雙軌） |
| `hooks.py` | `run_pre_llm_hook` / `run_post_llm_hook` 整合層 |
| `render.py` | `render_temporal_block` 產生 LLM prompt block |
| `persona_config/` | 各角色的參數設定（目前標配 `akane`） |

---

## 核心概念

### 時間區間（Time Period）

```
deep_night : 00:00–03:59
dawn       : 04:00–06:59
morning    : 07:00–11:59
afternoon  : 12:00–17:59
evening    : 18:00–21:59
night      : 22:00–23:59
```

### 睡眠壓力（Sleep Pressure）

Gaussian 曲線，凌晨 2:00 達到巔峰（1.0），下午最低（0.02）。

### 脆弱窗口（Vulnerability Window）

角色有各自的深夜區間（`vulnerability_hour_start` / `vulnerability_hour_end`）與沉默門檻（`vulnerability_silence_min`）。同時滿足兩者才會觸發。

### 情緒抑制（Emotional Inhibition）

沉默越久，抑制越高。72 小時以上可達 0.88。脆弱窗口與睡眠剝奪都會降低抑制，讓角色更容易流露心裡話。

### 情感攜帶（Emotional Carryover）

跨 session 保留：`intimacy_afterglow`、`unresolved_worry`、`emotional_openness_residue`、`attachment_heat`。每個角色有自己的 `decay_rate`（茜 0.08，预设 0.12）。

---

## 快速開始

```bash
pip install -e .
```

```python
from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.persona_config.akane import AKANE

# 每次 LLM 呼叫前
ctx, block, stress = run_pre_llm_hook(
    persona_id="akane",
    config=AKANE,
    last_msg_ts="2026-05-28T02:30:00+09:00",
    stress=50,
    db_path="./data/chrono_memory.db",
)
# block → 注入 system prompt
# stress → 用新版計算值替換舊版

# 每次 LLM 回覆後
run_post_llm_hook(ctx, config=AKANE, user_message="我沒事啦", db_path=db_path)
```

---

## 專案結構

```
chrono_social_engine/
├── core.py                   # 核心資料結構 + 計算函數
├── db.py                     # SQLite 持久化
├── resolver.py                # resolved event 偵測
├── hooks.py                  # pre/post LLM hook
├── render.py                 # temporal block 渲染
├── persona_config/
│   ├── config.py             # PersonaConfig dataclass（本體）
│   └── akane.py              # 黒川あかね 角色參數
data/
└── .gitkeep                  # SQLite DB 目錄
```

---

## 測試覆蓋

```
74 tests across 5 modules
├── test_core.py           35  核心邏輯
├── test_resolver.py       18  keyword + ctx 雙軌偵測
├── test_db.py              7  CRUD + upsert + timezone
├── test_hooks.py           5  lifecycle
└── test_integration_smoke.py  3  全鏈路冒煙測試
```

```bash
pytest tests/ -v
```

---

## 整合階段（三階段策略）

```
Stage 1 — Parallel Run（並行觀察，不影響現有行為）
Stage 2 — Shadow Mode（新版 block 插入 prompt，舊版仍主控）
Stage 3 — Full Switch（新版完全接管，移除舊版）
```

詳見 `CLAUDE.md` Phase 8 章節。

---

## 角色設定範例（akane.py）

```python
AKANE = PersonaConfig(
    persona_id="akane",
    decay_rate=0.08,                        # 記性好，衰退慢
    vulnerability_hour_start=22,              # 22:00 開始
    vulnerability_hour_end=4,                # 04:00 結束（跨越午夜）
    vulnerability_inhibition_threshold=0.45,  # 比較難打開
    vulnerability_silence_min=4.5,            # 需要 4.5 小時沉默才觸發
    worry_resolution_delta=0.65,
    attachment_heat_bump=0.12,
)
```

---

## License

MIT