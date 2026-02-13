# Tile Calculator (Pythonista)

A draggable tile-based calculator built in Pythonista (iOS).  
You build expressions by dragging and merging tiles on a grid—numbers, operators, fractions, roots, split tools, and substitution tiles.

## Core ideas
- **Tiles are the interface**: drag to combine, drop to evaluate, split to decompose.
- **`expr_str` is the truth**: tiles store a SymPy-safe expression string; labels are display-only.
- **Pretty rendering**: output is formatted for humans (×, 𝑥, no `*`, compact powers, √).

## Controls (high level)
- Drag tiles from the top spawners into the board.
- Drop one tile onto another to trigger a merge (depending on types).
- Special tools:
  - **Split (✂)**: decomposes fractions and surds (and other supported forms).
  - **Root (√)**: defaults to square root when applied; can be bound to nth root by dropping a number onto it.
  - **Substitution (x=)**: bind a value (x=3), then apply to expressions and fractions.

## Notes on = (equals)
This project uses "drop to compute" rather than a classic equals button.
- Results appear when merges resolve an expression.
- (TODO: verify) The equals tile may function as a merge trigger rather than a press-to-render.


## Refactor status

The app has now been split into multiple modules so features can be added in isolated files instead of one monolithic script.

Current structure:
- `Tile calc working copy.py` — tiny launcher/entrypoint
- `app_main.py` — app shell (`DragTestApp`) + `run_app()`
- `board.py` — `Board` orchestration and merge/evaluation flow
- `tile_models.py` — tile/spawner view classes
- `editor_views.py` — tile editor popup + overlay
- `board_menus.py` — trash/context menu components
- `widgets.py` — reusable UI button widgets
- `constants.py` — theme, sizing, color tokens
- `ui_utils.py` — shared geometry/touch helpers

This keeps behavior the same while making future feature work easier to place in the right file.

## Running
- Open the script in Pythonista and run.
- Recommended: iPad for space, but works on iPhone.

## Known design constraints
- Pythonista view colors must be **string hex** or **RGBA tuple**.
- Display “𝑥” is visual-only; internal math uses plain `x`.

## Documentation
See:
- `docs/ARCHITECTURE.md`
- `docs/TILE_TYPES.md`
- `docs/BEHAVIOR_SPEC.md`
- `docs/PATCH_WORKFLOW.md`

# Architecture

This project is best understood as a small UI + language engine:

- **UI layer**: tiles are `ui.View` objects with drag/drop.
- **Math layer**: internal expressions use SymPy-friendly strings (`expr_str`).
- **Routing layer**: merge logic is centralized in the board’s drop handler.

## Key objects (conceptual)
- **Board**: owns tiles, resolves drops, spawns results, and applies “tool” tiles.
- **Tile**: base tile view (numbers, operators, expressions, results, tools).
- **FractionTile**: specialized tile with numerator/denominator labels and fraction-aware behavior.
- **Spawner**: top-row “tile factories” (digits, operators, tools).

## Drag lifecycle (simplified)
1. `touch_began`: store start state
2. `touch_moved`: move tile, highlight/preview overlaps (optional)
3. `touch_ended`: finalize -> calls `Board.finalize_drop(tile)` (or equivalent)

## Drop routing
Drop routing is performed by a central method:
- `Board.finalize_drop(tile)`

It routes based on `tile.kind` and overlap target:
- `split` / `supersplit`: split logic first, fallback to generic split
- `root`: root binding or evaluation
- `subst`: bind x=value or apply substitution
- fractions/expr/number merges: expression building + evaluation
- result spawning: centralized in `_spawn_eval_result(val, x, y)` (or equivalent)

## Result spawning
All “computed results” should flow through:
- `Board._spawn_eval_result(val, x, y)`

Important behaviour:
- If SymPy result has **denominator ≠ 1**, spawn a **FractionTile** (even if it contains symbols).
- Otherwise spawn a normal result tile or expr tile.

## Rendering pipeline
Rules:
- `expr_str` stays SymPy-safe (plain `x`, `*`, `**` etc.)
- labels are display-only and are “pretty printed”
- `pretty_x_text()` ensures math-x appears as 𝑥 in UI
- `_sympy_pretty_label(expr)` removes `*` for humans, uses √, powers, π etc.

## Sizing behaviour
- Expression tiles widen based on measured display width.
- Fraction tiles widen based on max(display width of numerator/denominator), capped at 2-wide currently.

## Safety / robustness notes
- Always normalize color inputs (Pythonista expects tuple/string).
- Avoid setting `label.text` directly; prefer `Tile.set_label()` so 𝑥 + sizing rules apply.

# Tile Types

Tiles have a `kind` plus a few key fields.  
The most important invariant: **`expr_str` is canonical** (SymPy-safe), while labels are for display.

## Common fields
- `kind`: tile category (string)
- `expr_str`: internal expression string (SymPy-friendly)
- `label_text`: raw label text (often same as expr_str but not always)
- `tile_color`: base color; `background_color` uses normalized form

## Base kinds

### number
Represents a plain integer (and sometimes generic numeric).
- `expr_str`: `"7"`
- Display: `"7"`
- Color: number color
- Merge: with operators, fractions, roots, etc.

### op
Represents a binary operator (e.g. +, −, ×, ÷).
- `expr_str`: `"+"` or `"*"` or `"/"`
- Display: uses × and ÷ for * and /.
- Merge: combines two tiles into a new expression/result.

**Important UI rule**
- The visible ÷ spawner currently defaults to spawning an **empty fraction tile**.
- “Division operator” is available as the alternative form.

### expr
Represents symbolic expressions.
- `expr_str`: SymPy-safe, e.g. `"x**2 + 3*x + 1"`
- Display: pretty-printed, shows 𝑥, ×, removes `*` in simple products.

### result
Represents evaluated output (integer/decimal).
- `expr_str`: typically numeric string
- Color: result color (int/dec variants)

### fraction
Represents numerator/denominator with fraction-aware display.
- `numer`: raw numerator string or int
- `denom`: raw denominator string or int
- `expr_str`: `"(<numer>)/(<denom>)"` when complete
- Display: numerator/denominator rendered via SymPy pretty printing
- Color:
  - plain fractions: fraction color
  - if numer/denom contain x: expression color (EXPR_HEX)

**Sizing**
- 1-wide unless display text requires widening
- 2-wide (2x1) when numerator or denominator display text exceeds one-tile width

### root
Represents √ or nth root operator.
- Unbound root behaves like sqrt when applied to a target.
- Binding: drop number 2–9 onto root to convert to ²√, ³√, etc.
- Applying: root dropped onto target defaults to sqrt of target.

### split / supersplit
Tool tile used to decompose supported forms.
Special supported splits:
- fractions: pop denominator first, then numerator
- surds: split a*sqrt(b) into [a] [sqrt(b)]
- sqrt(b) into [√] [b]
(TODO: list any additional supported split targets)

### subst
Substitution tile (x=).
- Unbound: displays “x=” and becomes bound when merged with a number/result
- Bound: stores `subst_val` (SymPy value) and can be applied to expr/fraction tiles


# Behavior Spec

This doc describes intended behaviour. Implementation may evolve, but behaviour should stay consistent.

## 1) Pretty rendering rules
- Display uses:
  - `×` instead of `*`
  - `÷` for division operator display
  - `𝑥` for variable x (display only)
  - compact powers (² ³ …) where supported
  - √ where supported
- Internal math (`expr_str`) always uses plain `x` and SymPy syntax.

## 2) Fraction behaviour

### 2.1 Creating fractions
- Default “÷” spawner creates an **empty fraction tile**.
- Alternative form provides division operator behaviour.

### 2.2 Fraction results
If a merge/evaluation yields a SymPy expression with denominator ≠ 1:
- spawn a **fraction tile result** (even if expression contains x)

### 2.3 Fraction display + sizing
- Numerator/denominator are displayed with SymPy pretty rendering.
- Fraction widens to 2-wide only if the displayed text does not fit 1-wide.

### 2.4 Fraction coloring
- If numerator or denominator contains x → fraction uses expression color (EXPR_HEX).
- Otherwise uses normal fraction color.

## 3) Split behaviour

### 3.1 Fractions
- Split on a fraction with both parts present:
  1) first split pops denominator into a new tile
  2) second split pops numerator
- Spawned tiles:
  - numeric -> number tile
  - symbolic -> expr tile
- Fraction tile retains remaining part until fully emptied.

### 3.2 Surds / roots
- Split on `a*sqrt(b)` yields:
  - `[a]` and `[sqrt(b)]`
- Split on `sqrt(b)` yields:
  - `[√]` and `[b]`
- If coefficient is 1, do not create a useless `1` tile.
(TODO: verify current behaviour for coeff=1)

## 4) Root behaviour
- If **root tile is dragged onto a target** and is unbound: treat as **square root** of target.
- If **a number is dragged onto an unbound root**:
  - if number is 2–9: bind root degree (²√, ³√, …)
  - else: apply sqrt to that number

## 5) Substitution (x=) behaviour

### 5.1 Binding
- Drag unbound x= onto a number/result -> becomes x=<value>
- Stores the bound SymPy value in `subst_val`.

### 5.2 Applying to expressions
- Drag bound x=value onto expr tile -> spawns evaluated result tile
- Original expression may remain (non-destructive) depending on design (TODO: confirm).

### 5.3 Applying to fractions
- Drag bound x=value onto fraction with (numer, denom):
  - substitute into numerator and denominator separately
  - simplify
  - spawn result via the same result spawning rules (fraction if denom ≠ 1)
Example:
- x=3 on x^2/4 -> 9/4 as a fraction tile

# Patch Workflow

This project is maintained via a patching tool that applies targeted REPLACE/INSERT edits.
The goal is to keep changes surgical and avoid destabilizing drag/merge flows.

## Golden rules
1. **Never break the drop router** (`Board.finalize_drop` or equivalent).
2. **`expr_str` is canonical**. Do not put 𝑥 into expr_str.
3. **All display text should go through `set_label()` or pretty rendering**.
4. **Normalize colors** before assigning to `background_color`.

## High-risk choke points
- Drop routing: `finalize_drop`
- Result creation: `_spawn_eval_result`
- Pretty printing: `_sympy_pretty_label` + `pretty_x_text`
- Fraction display: `FractionTile._refresh_display`
- Any code that assigns `label.text = ...` directly

## Regression test checklist (quick)
After any patch that touches merge/split/root/subst:
- Merge number + op + number -> correct result spawns
- Multiply two fractions -> fraction result spawns
- Subst x=3 on expr -> evaluated result spawns
- Subst x=3 on fraction -> fraction result spawns
- Split on fraction pops denom then numer
- Split on a*sqrt(b) -> [a] [sqrt(b)]
- Drag unbound root onto target -> sqrt(target)
- Drag 3 onto root -> cube root operator
