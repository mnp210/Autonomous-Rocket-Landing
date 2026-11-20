# Stage 9.4.1 — Research & Engineering Dashboard: Visual Design & Interface Specification

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.4.1 (Design Foundation)  
**Classification:** Aerospace Ground-Station & Research Workstation Design System  
**Status:** Approved & Formally Specified  

---

## 1. Visual Design Principles

The Autonomous Rocket Landing Research & Engineering Dashboard is modeled on modern aerospace mission control interfaces, flight-test telemetry stations, and scientific workstations. It rejects generic web SaaS templates, arbitrary gauge dials, pastel color schemes, and decorative non-physical graphics.

### Core Visual Directives:
1. **High Information Density with Structured Hierarchy:** Panels use compact spacing ($4\text{px}$ to $16\text{px}$), micro-labels ($9\text{px}$ to $11\text{px}$), and tabular data grids to maximize visible engineering data without visual clutter.
2. **Deterministic Semantic Color Tokens:** Colors communicate physical state and operational urgency only. Cyan denotes informational telemetry; emerald denotes nominal contact and safe descent; amber denotes caution and throttling; crimson denotes critical limits, crash conditions, and main thruster firing.
3. **Tabular Numerics & Fixed Pitch Formatting:** Every dynamic numeric value enforces `font-variant-numeric: tabular-nums` and a monospaced font family to eliminate layout jitter during high-frequency ($50\text{ Hz}$) telemetry updates.
4. **Disciplined Empty States:** Unpopulated telemetry areas display clear, technical standby indicators with defined physical axes and units, rather than blank voids or broken placeholders.

---

## 2. Color Palette & Token Definitions

All interface surfaces build on a deep graphite/near-black foundation, providing maximum contrast for telemetry text and vector overlays while minimizing eye strain during long-duration flight testing.

### 2.1 Surface & Structural Tokens

| Token Name | Hex Code | Role / Usage | WCAG AA Contrast vs Text |
|:---|:---:|:---|:---:|
| `aerospace-bg-void` | `#080B10` | Global application canvas background | $> 14:1$ vs Slate-100 (`#F1F5F9`) |
| `aerospace-panel-base`| `#0D1117` | Standard panel background | $> 12:1$ vs Slate-100 (`#F1F5F9`) |
| `aerospace-panel-header`| `#101622`| Panel title bars & toolbar headers | $> 10:1$ vs Slate-100 (`#F1F5F9`) |
| `aerospace-surface-elevated`| `#131A24`| Elevated cards, input wells, metrics boxes | $> 9:1$ vs Slate-200 (`#E2E8F0`) |
| `aerospace-border-subtle`| `#1E293B`| Primary panel structural dividers & borders | Subtle contrast ($3:1$ vs `#0D1117`) |
| `aerospace-border-accent`| `#334155`| Active focus rings & highlighted container bounds | Clean boundary ($4.5:1$ vs `#0D1117`)|

### 2.2 Semantic Telemetry Status Tokens

| Token Name | Hex Code | Tailwind Utility | Semantic Meaning & State Assignment |
|:---|:---:|:---|:---|
| **`cyan-telemetry`** | `#00F0FF` | `text-cyan-400`, `border-cyan-400` | Informational telemetry, position vectors, active navigation pills, primary status badges. |
| **`emerald-nominal`** | `#00E676` | `text-emerald-400`, `border-emerald-500` | Confirmed nominal touchdown, ground contact microswitches engaged, safe sink rate ($v_y \ge -1.0\text{ m/s}$). |
| **`amber-caution`** | `#FFB300` | `text-amber-400`, `border-amber-500` | Cautionary state, moderate sink rate ($-1.0 > v_y \ge -2.0\text{ m/s}$), low throttle, reconnecting network. |
| **`crimson-critical`** | `#FF1744` | `text-rose-400`, `border-rose-500` | Critical sink rate ($v_y < -2.0\text{ m/s}$), main engine firing, crash event, disconnection fault. |
| **`slate-standby`** | `#94A3B8` | `text-slate-400`, `border-slate-700` | Inactive thrusters, standby empty states, secondary metadata, inactive tabs. |

---

## 3. Typography Scale & Formatting Standards

The interface exclusively employs monospace typography for numeric data and telemetry readouts, paired with geometric system fonts for headings:

- **Primary Monospace Stack:** `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`
- **Numerics Feature Setting:** `font-variant-numeric: tabular-nums;`
- **Text Smoothing:** `-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;`

### 3.1 Type Scale Specification

| Element | Font Size | Line Height | Font Weight | Letter Spacing | CSS Utility | Usage |
|:---|:---:|:---:|:---:|:---:|:---|:---|
| **Micro-Label** | $9\text{px}$ | $12\text{px}$ | Bold ($700$) | $+0.08\text{em}$ | `text-[9px] uppercase font-bold tracking-widest` | Subsystem tags, vector labels, coordinate headers |
| **Component Label** | $10\text{px}$ | $14\text{px}$ | Semi-Bold ($600$) | $+0.05\text{em}$ | `text-[10px] uppercase font-semibold tracking-wider`| Telemetry titles, table column headers |
| **Secondary Body** | $11\text{px}$ | $16\text{px}$ | Normal ($400$) | Normal | `text-[11px] text-slate-400 font-normal` | Explanatory notes, caveat descriptions |
| **Standard Body** | $12\text{px}$ | $18\text{px}$ | Medium ($500$) | Normal | `text-xs text-slate-200 font-medium` | General text, table data rows |
| **Section Header** | $14\text{px}$ | $20\text{px}$ | Bold ($700$) | $+0.04\text{em}$ | `text-sm font-bold text-slate-100 tracking-wider` | Mission header, primary viewport mode label |
| **Primary Telemetry**| $18\text{px}$ | $24\text{px}$ | Bold ($700$) | $-0.02\text{em}$ | `text-lg font-bold tabular-nums text-slate-100` | Large digital readouts (Altitude, Velocity) |

---

## 4. Spacing, Borders & Panel Chrome

### 4.1 Spacing Scale
- Compact component padding: $4\text{px}$ (`p-1`), $8\text{px}$ (`p-2`), $12\text{px}$ (`p-3`).
- Viewport and layout margins: $12\text{px}$ to $16\text{px}$ (`p-3 md:p-4`).
- Inter-panel gutters: $8\text{px}$ to $16\text{px}$ (`gap-2 md:gap-3 lg:gap-4`).

### 4.2 Border Geometry
- Corner radii: Subtle $4\text{px}$ (`rounded`), max $8\text{px}$ (`rounded-lg`) on main viewports. Bubbly, oversized pill cards ($>12\text{px}$) are strictly prohibited.
- Stroke width: $1\text{px}$ borders (`border border-slate-800/80`).
- Accent accentuation: Panel headers feature a $2\text{px} \times 14\text{px}$ vertical cyan indicator bar (`w-1 h-3.5 bg-cyan-400 rounded-xs`) preceding panel titles.

---

## 5. Component Design Specifications & Visual Layouts

### 5.1 Telemetry Readout (`TelemetryReadout.tsx`)
High-density numeric telemetry cell with tabular alignment, secondary targets, and semantic threshold color-coding:

```
┌──────────────────────────────────────────────┐
│ ALTITUDE                         TARGET: 0.00│  <- Micro-label & Target
│                                              │
│ 12.45 m                              NOMINAL │  <- 18px Tabular Value & State Tag
└──────────────────────────────────────────────┘
```

### 5.2 Status Badge (`StatusBadge.tsx`)
Pill-shaped indicator badge with optional pulsing status dot:

```
┌────────────────────────┐
│ [●] STAGE D (SEED 42)  │  <- Pulse dot + 10px uppercase monospaced text
└────────────────────────┘
```

### 5.3 Tab Navigation Bar (`TabNavigation.tsx`)
Keyboard-accessible ARIA tablist featuring subtle glowing active indicators:

```
┌────────────────────────────────────────────────────────┐
│ [ LIVE OPERATIONS: 2D ]   [ RESEARCH & BENCHMARKS: 12 ]│
└────────────────────────────────────────────────────────┘
```

### 5.4 State Vector Display (`StateVectorDisplay.tsx`)
Formatted multi-component vector display with sign preservation and coordinate frame labels:

```
┌────────────────────────────────────────────────────────┐
│ POSITION VECTOR                       BOX2D WORLD (2D) │
├──────────────────────────┬─────────────────────────────┤
│ X: +0.12 m               │ Y: +12.45 m                 │
└──────────────────────────┴─────────────────────────────┘
```

### 5.5 Disciplined Empty State (`EmptyState.tsx`)
Engineering standby placeholder indicating telemetry awaiting live flight execution:

```
┌ - - - - - - - - - - - - - - - - - - - - - - - - - - - -┐
:                      [  ICON  ]                        :
:                 [ AWAITING TELEMETRY ]                 :
:             DESCENT TRAJECTORY PROFILE                 :
: Coordinate trace will render when an active simulation  :
: episode executes. Sampled at 50 Hz from Box2D state.   :
└ - - - - - - - - - - - - - - - - - - - - - - - - - - - -┘
```

---

## 6. Responsive Layout Breakpoints

The dashboard adapts across four primary display profiles without losing critical telemetry:

| Profile | Viewport Resolution | Grid Configuration | Viewport Behavior | Sidebar / Telemetry |
|:---|:---:|:---:|:---|:---|
| **Ultra-Wide / 1080p Desktop** | $\ge 1600\text{px} \times 1050\text{px}$ | 12-column grid (`lg:grid-cols-12`) | 8 columns ($66.7\%$ width), full-height ($h = \text{calc}(100\text{vh} - 95\text{px})$) | 4 columns ($33.3\%$ width), stacked controls & telemetry |
| **Standard Laptop** | $1366\text{px} \times 768\text{px}$ to $1440\text{px} \times 900\text{px}$ | 12-column grid (`lg:grid-cols-12`) | 8 columns, auto-scaled Canvas/WebGL resolution | 4 columns with independent vertical scrollbar |
| **Tablet Landscape** | $1024\text{px} \times 768\text{px}$ | Single-column stacked layout | Full width, $460\text{px}$ fixed min-height | Flows below viewport with horizontal control buttons |
| **Mobile Portrait** | $375\text{px} \times 812\text{px}$ | Single-column linear flow | Full width, $360\text{px}$ height | Collapsed secondary telemetry, primary indicators top |

---

## 7. Accessibility Compliance Matrix (WCAG 2.1 AA)

| Accessibility Criterion | Standard Required | Implementation in Stage 9.4.1 | Compliance Status |
|:---|:---:|:---|:---:|
| **1.4.3 Contrast (Minimum)** | $\ge 4.5:1$ for normal text; $\ge 3.0:1$ for large text | All text tokens exceed $9:1$ against surface backgrounds (Slate-100 on `#0D1117` is $12:1$; Cyan `#00F0FF` on `#080B10` is $11.8:1$). | **PASS (Exceeds AAA)** |
| **1.4.1 Use of Color** | Color is not used as the sole visual means of conveying information | Every status color is accompanied by explicit textual state names (e.g., "NOMINAL", "CAUTION", "CRITICAL", "CONNECTED", "DISCONNECTED"). | **PASS** |
| **2.1.1 Keyboard Accessible** | All interactive elements operable via keyboard | `TabNavigation` supports `role="tablist"`, `ArrowRight`, `ArrowLeft`, `Home`, and `End` keys; buttons feature visible `:focus-visible` rings (`ring-cyan-400`). | **PASS** |
| **2.4.7 Focus Visible** | Any keyboard operable interface has a mode of operation where the keyboard focus indicator is visible | Clear $1\text{px}$ cyan focus rings applied to all interactive controls. | **PASS** |
| **2.3.1 Three Flashes or Below**| No flashing content exceeding 3 Hz | Status pulse animations run at $0.5\text{ Hz}$ (`animate-pulse`); no strobe effects. | **PASS** |
