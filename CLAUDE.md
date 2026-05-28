# Project: chrono-social-engine
**目標**：建立一個通用的時間-社交感知引擎，可為多個角色提供長期情感記憶與時間節奏計算，最終整合進 Hermes Agent 框架。

---

## 📁 專案結構

```
chrono-social-engine/
├── CLAUDE.md ← 本文件
├── README.md
├── pyproject.toml
├── chrono_social_engine/
│   ├── __init__.py
│   ├── core.py          ← 主要資料結構與計算邏輯
│   ├── db.py             ← SQLite 持久化層
│   ├── hooks.py          ← run_pre_llm_hook / run_post_llm_hook
│   ├── resolver.py       ← resolved_event 自動偵測
│   ├── render.py         ← render_temporal_block + situation_hint
│   └── persona_config/
│       ├── __init__.py   ← PersonaConfig dataclass
│       ├── akane.py      ← 茜的設定
│       └── _template.py  ← 新角色設定範本
├── tests/
│   ├── test_core.py
│   ├── test_db.py
│   ├── test_hooks.py
│   └── test_resolver.py
└── data/
    └── chrono_memory.db  ← SQLite（gitignore）
```

---

## 🏗️ Phase 1 — 核心模組建立

### `chrono_social_engine/core.py`

主要資料結構：

```python
@dataclass
class TemporalContext:
    persona_id: str
    current_hour: int
    time_period: str          # dawn/morning/afternoon/evening/night/deep_night
    silence_hours: float
    carryover: EmotionalCarryover
    momentum: MomentumState
    anticipatory: AnticipatoryState
    deviation_interpretation: str  # normal/sleep_deprivation/longing/missing
    emotional_inhibition: float    # 0.0~1.0
    stress: int                   # 0~100

@dataclass
class EmotionalCarryover:
    intimacy_afterglow: float         # 0.0~1.0
    unresolved_worry: float           # 0.0~1.0
    emotional_openness_residue: float  # 0.0~1.0
    attachment_heat: float           # 0.0~1.0
    source_event: str
    triggered_at: str                # ISO 8601
    decay_rate: float                 # 從 PersonaConfig 帶入

@dataclass
class MomentumState:
    vulnerability_window: bool
    emotional_amplification: float     # <0 抑制, >0 放大

@dataclass
class AnticipatoryState:
    preoccupation_flavor: str  # none/longing/worried/anxious
    expected_presence_prob: float
    silence_hours: float

TIME_PERIODS = [
    (4, 7,  "dawn"),       # 04:00–06:59
    (7, 12,  "morning"),   # 07:00–11:59
    (12, 18, "afternoon"), # 12:00–17:59
    (18, 22, "evening"),  # 18:00–21:59
    (22, 24, "night"),     # 22:00–23:59
    (0, 4,  "deep_night"), # 00:00–03:59
]
```

**計算函數**：
- `compute_time_period(hour: int) -> str` — 查表
- `compute_sleep_pressure(current_hour: int) -> float` — 鐘形曲線，凌晨最高
- `compute_emotional_inhibition(ctx: TemporalContext, config: PersonaConfig) -> float`
- `compute_vulnerability_window(ctx: TemporalContext, config: PersonaConfig) -> bool`
- `build_temporal_context(persona_id, last_msg_ts, stress, carryover, config) -> TemporalContext`
- `merge_carryover(existing: EmotionalCarryover, new: EmotionalCarryover) -> EmotionalCarryover`
- `decay_carryover(carryover: EmotionalCarryover, elapsed_hours: float) -> EmotionalCarryover`

**注意事項**：
- `TIME_PERIODS` 每個條目是 `(start_hour, end_hour, name)`，end_hour 不包含在區間內
- `compute_sleep_pressure` 的鐘形曲線資料（hour → pressure）要改成 module-level tuple list 或用 `@lru_cache`，避免每次重建
- `compute_emotional_inhibition` 中的 `range` dict 改成 module-level 常數

---

## 🗄️ Phase 2 — 持久化層

### `chrono_social_engine/db.py`

```python
def init_db(db_path: Path = DB_PATH) -> None
def load_carryover_from_db(persona_id: str, db_path: Path) -> EmotionalCarryover | None
def save_carryover_to_db(carryover: EmotionalCarryover, persona_id: str, db_path: Path) -> None
```

**Schema**：
```sql
CREATE TABLE IF NOT EXISTS emotional_carryover (
    persona_id                  TEXT PRIMARY KEY,
    intimacy_afterglow          REAL DEFAULT 0.0,
    unresolved_worry            REAL DEFAULT 0.0,
    emotional_openness_residue  REAL DEFAULT 0.0,
    attachment_heat             REAL DEFAULT 0.0,
    source_event               TEXT DEFAULT '',
    triggered_at               TEXT NOT NULL,
    decay_rate                 REAL DEFAULT 0.12
);
```

**要求**：
- 使用 `INSERT INTO ... ON CONFLICT(persona_id) DO UPDATE SET ...` 做 upsert
- `triggered_at` 存 ISO 8601（`datetime.isoformat()`）
- `load_carryover_from_db` 任何 exception 靜默回傳 `None`，不 raise

---

## 🤖 Phase 3 — resolved_event 自動偵測

### `chrono_social_engine/resolver.py`

實作 `detect_resolved_event(user_message: str, ctx: TemporalContext) -> str | None`

偵測規則（keyword + context 雙重確認）：

```python
RESOLUTION_PATTERNS = {
    "user_confirmed_ok": [
        ["沒事", "還好", "好多了", "放心", "不用擔心", "我沒事"],
        ["fine", "ok", "okay", "better", "don't worry", "i'm good"],
    ],
    "explicit_reassurance": [
        ["謝謝你擔心", "知道了", "會注意", "你放心"],
    ],
}
```

**`user_slept_normally` 的邏輯**（不看 keyword，看 ctx）：
- 條件：`ctx.time_period in ("morning", "dawn")` AND `ctx.carryover.unresolved_worry > 0.3` AND `ctx.silence_hours > 5`
- 代表上次深夜有 worry，這次早上才出現，代表中間有睡，worry 可以部分解除

---

## 🔗 Phase 4 — Hooks

### `chrono_social_engine/hooks.py`

```python
def run_pre_llm_hook(
    persona_id: str,
    config: PersonaConfig,
    last_msg_ts: str | None,
    stress: int,
    db_path: Path = DB_PATH,
) -> tuple[TemporalContext, str, int]:
    """
    回傳：(ctx, temporal_block_string, adjusted_stress)
    temporal_block_string 直接插入 system prompt
    """

def run_post_llm_hook(
    ctx: TemporalContext,
    config: PersonaConfig,
    user_message: str,
    db_path: Path = DB_PATH,
) -> None:
    """
    1. detect_resolved_event(user_message, ctx)
    2. create_carryover_if_needed(ctx, now)
    3. merge or replace
    4. resolve_worry_if_applicable
    5. save_carryover_to_db
    """
```

**所有函數都接受 `config: PersonaConfig` 參數，引擎本體不帶任何角色假設。**

---

## 🎨 Phase 5 — Render

### `chrono_social_engine/render.py`

```python
def render_temporal_block(ctx: TemporalContext) -> str
def _generate_situation_hint(ctx: TemporalContext) -> str
```

**Situation Hint 規則**（依優先序，最多輸出 2 條）：

```python
HINT_PRIORITY = [
    (lambda ctx: ctx.momentum.vulnerability_window,
        "深夜防衛低落，容易說出平時不會說的話"),
    (lambda ctx: ctx.carryover.unresolved_worry > 0.5,
        lambda ctx: f"仍在擔心上次對話（{ctx.carryover.source_event}）"),
    (lambda ctx: ctx.deviation_interpretation == "sleep_deprivation",
        "對方這時間仍在線，推測睡眠不足"),
    (lambda ctx: ctx.anticipatory.preoccupation_flavor == "longing",
        "對方消失超過一天，有明顯思念"),
    (lambda ctx: ctx.anticipatory.preoccupation_flavor == "worried",
        "正在等待對方，有擔心傾向"),
]
```

---

## 👤 Phase 6 — PersonaConfig 系統

### `chrono_social_engine/persona_config/__init__.py`

```python
@dataclass
class PersonaConfig:
    persona_id: str
    decay_rate: float = 0.12
    vulnerability_hour_start: int = 22   # 深夜區間 start
    vulnerability_hour_end: int = 4       # 深夜區間 end（跨越午夜）
    vulnerability_inhibition_threshold: float = 0.50
    vulnerability_silence_min: float = 4.0
    worry_resolution_delta: float = 0.6
    attachment_heat_bump: float = 0.1
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/New_York"))  # 使用者所在時區，影響所有時間感知計算。EST/EDT 自動切換
```

### `chrono_social_engine/persona_config/akane.py`

```python
AKANE = PersonaConfig(
    persona_id="akane",
    decay_rate=0.08,                        # 記性好，衰退慢
    vulnerability_inhibition_threshold=0.45,
    vulnerability_silence_min=4.5,
)
```

### `chrono_social_engine/persona_config/_template.py`

新角色設定範本：

```python
# 複製此檔並改 名稱 + 數值即可新增角色
TEMPLATE = PersonaConfig(
    persona_id="new_character",
    decay_rate=0.12,       # 參考值，可調整
)
```

---

## ✅ Phase 7 — 測試

### `tests/test_core.py`

覆蓋以下 case：

```python
def test_vulnerability_window_deep_night():
    """凌晨3點 + silence > 4h → vulnerability_window = True"""

def test_vulnerability_window_daytime_no_trigger():
    """下午3點 + silence 10h → vulnerability_window = False"""

def test_emotional_inhibition_floor():
    """silence_hours = 200 → emotional_inhibition >= 0.05"""

def test_sleep_pressure_curve():
    """凌晨2點=1.0, 下午3點=0.05, 晚上10點=0.55"""

def test_carryover_decay():
    """12小時後 intimacy_afterglow 應該衰退約 (1-0.12)^12 ≈ 0.20 倍"""

def test_unresolved_worry_floor():
    """無論衰退多久，unresolved_worry >= original * 0.25"""

def test_carryover_merge_no_overflow():
    """多次 merge 後所有值 <= 1.0"""

def test_carryover_triggers_combined():
    """vuln + sleep_dep 同時觸發 → unresolved_worry = max(0.15, 0.85) = 0.85"""

def test_persona_config_akane_params():
    """AKANE config 的 decay_rate 應該是 0.08，不是預設值"""

def test_persona_config_generic_engine():
    """engine functions 接受不同 config，結果合理差異化"""
```

### `tests/test_resolver.py`

```python
def test_user_confirmed_ok_zh():
    assert detect_resolved_event("沒事啦放心", mock_ctx) == "user_confirmed_ok"

def test_user_slept_normally():
    """morning ctx + silence > 5h + unresolved_worry > 0.3 → user_slept_normally"""

def test_no_resolution_neutral_message():
    assert detect_resolved_event("你好", mock_ctx) is None

def test_explicit_reassurance():
    assert detect_resolved_event("謝謝你担心，我没事", mock_ctx) == "explicit_reassurance"
```

---

## 📋 pyproject.toml

```toml
[project]
name = "chrono-social-engine"
version = "2.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[project.readme = "README.md"]
```

---

## 🔌 整合進 Hermes Agent 的步驟（Phase 8，人工完成）

每個角色的 plugin 做以下替換：

```python
from chrono_social_engine.hooks import run_pre_llm_hook, run_post_llm_hook
from chrono_social_engine.persona_config import AKANE  # 或其他角色

# pre
ctx, block, stress = run_pre_llm_hook(
    persona_id="akane",
    config=AKANE,
    last_msg_ts=last_msg_ts,
    stress=current_stress,
)
# block 插入 system prompt

# post
run_post_llm_hook(ctx, config=AKANE, user_message=user_input)
```

---

## ⚠️ 已知限制

- `RelationshipRhythm`（`shared_night_count`、`peak_intimacy_hour`）尚未實作，這是 v3 的工作
- `background_state_evolution`（無對話時的背景演化）尚未實作
- `expected_presence_prob` 目前是靜態值（0.6/0.3），v3 會改為動態計算

---

## v3 計畫（尚未實作，Stage 1 整合完成後再啟動）

### Event Causality Chain
- 新增 `TemporalEvent` dataclass 與對應 SQLite table
- `create_carryover_if_needed` 改為同時寫入 `temporal_events`
- 提供 `trace_event_chain(event_id)` 查詢函數
- 目標：讓「茜為什麼這樣回應」可以被追蹤與 debug

### PersonalRhythmProfile
- 從 temporal_events 歷史推算 `usual_sleep_hour` / `usual_wake_hour`
- 移動平均，alpha=0.15

### RelationshipRhythm
- `shared_night_count`、`peak_intimacy_hour`
- `background_state_evolution`（APScheduler）

> **執行原則**：Stage 1 整合完成後，讓真實對話跑一段時間，累積真實 debug 需求後再啟動 v3。

---

## 🎯 完成定義

- [ ] `pytest tests/` 全部通過
- [ ] `pytest --cov=chrono_social_engine` 覆蓋率 ≥ 85%
- [ ] `render_temporal_block` 輸出可被 LLM 正確解讀為角色行為提示
- [ ] 更換 `PersonaConfig` 後，引擎行為產生合理差異化（不同角色有不同衰退速度、深夜門檻等）
- [ ] 引擎本體 `core.py`、`db.py`、`hooks.py`、`resolver.py`、`render.py` 中不出现任何角色名稱字面量

---
## 開工指令

請閱讀 CLAUDE.md，按照 Phase 1 到 Phase 7 的順序逐步實作。
每個 Phase 完成後暫停，讓我確認後再繼續下一個。
從 Phase 1 開始。