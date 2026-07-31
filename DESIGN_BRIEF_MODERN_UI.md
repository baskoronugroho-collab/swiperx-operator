# SwipeRx Operator — UI modernization brief (27 Jul 2026)

> **Instruction (Baskoro):** make the app feel more modern, keep the colours the same.
> Scope: the deployed React app (operator console + courier wizard). This brief is the
> contract for the restyle; the implementation lives in `frontend/src/index.css`
> (tokens), `frontend/src/components/ui.tsx` (primitives), and `Shell.tsx`.

## 1. What this app is, and what "modern" means for it

Two surfaces, one identity:

- **Operator console** — desktop, used by DE/Implant staff moving fast between an Excel
  world and Ninja's systems. They live in tables of tracking codes.
- **Courier wizard** — a low-end Android phone, held one-handed at a pharmacy door in
  daylight, inside the Ninja driver-app webview.

"Modern" here is **not** decoration. It is: quieter chrome, stronger hierarchy, codes
treated as first-class objects, and status you can read at arm's length. The Ninja red
stays exactly what it is — but it gets *rarer*, which makes it louder.

## 2. Colour — unchanged values, redisciplined roles

| Token | Value | Role (the change is the role, not the hex) |
|---|---|---|
| `nv-red` | `#EE1B2C` | **Action + identity only**: primary buttons, active nav, focus rings, the brand hairline. Never a background wash. |
| `nv-red-dark` | `#C2141F` | hover/pressed |
| `nv-red-soft` | `#FDECEE` | active-nav tint, danger-adjacent fills |
| `ink` | `#1A1A1A` | text |
| `ink-muted` | `#6B7280` | secondary text |
| `canvas` / `surface` / `line` | `#F4F4F6` / `#FFFFFF` / `#E8E8EC` | canvas lightens one step (was `#E7E7EB`) so white cards float on it with a 1px border + whisper shadow instead of heavy boxes |
| status greens/ambers/blues | unchanged | see badges, §5 |

One new *treatment* (no new colour): a **2px `nv-red` hairline across the very top of
every page** — the quiet Ninja signature that replaces any need for red blocks.

## 3. Type — the personality change

Montserrat-for-everything reads 2019. The modern trio, all Google-hosted:

| Role | Face | Why |
|---|---|---|
| Display / nav / buttons | **Montserrat 600–700** | it *is* the NV identity — kept, but only where voice is needed |
| Body / tables / forms | **Inter** (400/500/600) | quieter, tighter, far better at 12–14px data sizes; tabular numerals for counts |
| **Codes** | **JetBrains Mono 500** | AWBs, POs, TIDs, tokens are the soul of this product and currently fall back to random system monospace |

Micro-labels (table headers, eyebrows): Inter 600, 11px, uppercase, +0.06em tracking.

## 4. The signature element — the **code chip**

Every tracking identifier (SwipeAWB, PO, TID, courier URL) renders one way, everywhere:
JetBrains Mono in a soft chip — `bg canvas-soft · 1px line border · radius 6 · 2px 6px
padding`. On the courier header the AWB chip is the hero: large, high-contrast, readable
at arm's length. This is the one element the app is remembered by, and it encodes
something true: *codes are the atoms of this business.*

Second, courier-only: a **segmented progress rail** under the wizard header — one thin
segment per phase, filled in `nv-red` as the courier advances. The flow genuinely is a
sequence, so the structure is honest, and it answers the courier's only real question:
*how much is left?*

## 5. Component rules

- **Cards**: radius 16, `1px line` border, `0 1px 2px rgb(0 0 0 / .04)` shadow. No
  heavier elevation anywhere.
- **Buttons**: radius 10, Montserrat 600, 150ms ease; primary red, ghost bordered,
  quiet text-only. Focus = 2px red ring at 20% + offset.
- **Status badges**: **dot + text** (coloured 6px dot, ink text) for neutral/ok/info
  states — filled pills survive **only for warnings and danger** ("Not acknowledged",
  "Retur semua"), so a filled shape always means *look at me*.
- **Tables**: header row = micro-label style on `canvas-soft`; body rows 13px Inter,
  `hover:bg-canvas-soft/60`, 1px separators, generous 12px vertical padding.
- **Header**: sticky, `surface/85` + backdrop-blur, brand hairline on top, logo tile
  radius 10. Nav active = `nv-red-soft` tint + red text (unchanged pattern, softer shape).
- **Inputs**: radius 10, border `line`, focus ring as buttons. Labels 13px Inter 600.

## 6. Motion

150ms ease on hover/focus everywhere; the courier wizard's phase change gets a single
6px rise + fade (180ms). Nothing else moves. `prefers-reduced-motion` disables both.

## 7. Explicitly rejected

- Dark mode, gradients, glassmorphism cards, red section backgrounds (colour discipline).
- Icon libraries — the app's vocabulary is text + codes; emoji stays only on the camera
  button where it aids recognition.
- Any layout change: page structure, routes and flows are untouched. This is a reskin
  at the token/primitive level, so every screen inherits it at once.

## 8. Quality floor

Responsive to 360px, visible keyboard focus, WCAG-AA contrast on all text (ink-muted on
canvas-soft passes at 13px+), reduced-motion respected, courier surface tested in a
375px viewport.
