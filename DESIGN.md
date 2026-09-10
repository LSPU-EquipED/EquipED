---
version: alpha
name: EquipED
description: Academic SLM Evaluation Workspace — Contemporary Faculty Ledger

colors:
  primary: "#1b3b87"
  primary-strong: "#142f70"
  primary-soft: "#edf2ff"
  primary-foreground: "#ffffff"
  secondary: "#f2c811"
  secondary-foreground: "#172033"
  accent: "#f2c811"
  accent-soft: "#fff8cf"
  accent-foreground: "#172033"
  success: "#2f7d32"
  success-soft: "#edf7ed"
  success-foreground: "#ffffff"
  info: "#1f718f"
  info-soft: "#eaf7fb"
  info-foreground: "#ffffff"
  warning: "#8a5a00"
  warning-soft: "#fff7db"
  warning-foreground: "#ffffff"
  destructive: "#b42318"
  destructive-soft: "#fff0ee"
  destructive-foreground: "#ffffff"
  canvas: "#f4f7fb"
  surface: "#ffffff"
  surface-subtle: "#f8fafc"
  text: "#172033"
  text-muted: "#596579"
  border: "#d6deea"
  border-strong: "#94a3b8"
  input: "#c8d2e1"
  ring: "#1b3b87"

typography:
  display:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.02em
  heading-lg:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: -0.015em
  heading-md:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: -0.01em
  heading-sm:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: normal
  body-md:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: normal
  body-sm:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: normal
  label-sm:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.04em
  data-md:
    fontFamily: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: normal

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px

rounded:
  none: 0px
  xs: 2px
  sm: 4px
  md: 6px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: 40px

  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    borderColor: "{colors.border}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: 40px

  button-destructive:
    backgroundColor: "{colors.destructive}"
    textColor: "{colors.destructive-foreground}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: 40px

  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    borderColor: "{colors.input}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
    height: 40px

  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    borderColor: "{colors.border}"
    rounded: "{rounded.md}"
    padding: "16px"

  table-header:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text-muted}"
    typography: "{typography.label-sm}"
    borderColor: "{colors.border}"
    padding: "8px 12px"

  table-cell:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body-sm}"
    borderColor: "{colors.border}"
    padding: "10px 12px"
---

# Design System: EquipED

## Overview

**Creative North Star: "The Contemporary Faculty Ledger"**

EquipED is an institutional evaluation and compliance workstation for Laguna State Polytechnic University (LSPU) faculty members and Curriculum Instruction Division (CID) staff reviewing Self-Paced Learning Modules (SLMs).

The visual language, "The Contemporary Faculty Ledger," treats evaluations as formal academic instruments. It pairs civic restraint with modern data density:
- **Tabular Rigor**: High-density grid cells, crisp 1px borders, and tabular figures for numbers, ratings, and weights.
- **Document-First Hierarchy**: Clean editorial typography using self-hosted Public Sans with sentence-case structure instead of shouting uppercase labels.
- **Quiet Trust**: Soft, calm canvas backgrounds (`#f4f7fb`) and white ledger surfaces that eliminate eye strain during multi-hour grading and review sessions.
- **Anti-Slop Discipline**: Rejection of generic AI templates, purple-blue gradients, floating glassmorphism cards, noisy textured backgrounds, and decorative micro-interactions.

---

## Colors

The palette is rooted in the official Laguna State Polytechnic University identity while strictly adhering to WCAG 2.1 AA contrast requirements across all semantic pairings.

### Brand Colors
- **LSPU Royal Blue (`#1b3b87`)**: The primary institutional color. Used for high-priority actions, active navigation boundaries, and focus rings. High-contrast white text is mandatory.
- **SCC Amber Gold (`#f2c811`)**: The secondary academic emblem color. Reserved for attention-attracting accents, alert banners, and active indicators. Amber text is paired with dark slate (`#172033`)—it must never be rendered against white backgrounds.

### Neutrals & Surfaces
- **Canvas (`#f4f7fb`)**: Cool institutional page backdrop that distinguishes floating modals and ledger cards without resorting to warm beige or harsh stark white.
- **Surface (`#ffffff`)**: Primary background for ledger tables, evaluation cards, and document reader panes.
- **Surface Subtle (`#f8fafc`)**: Neutral tint for table headers, inactive panel borders, and disabled controls.
- **Text / Foreground (`#172033`)**: Deep slate navy providing 15.1:1 contrast against canvas for high-fatigue reading sessions.
- **Text Muted (`#596579`)**: Muted secondary text providing 5.9:1 contrast on white surfaces for captions, timestamps, and column titles.
- **Border (`#d6deea`)**: 1px structural separator separating ledger cells and panel boundaries.
- **Input Border (`#c8d2e1`)**: Focused control boundary for form inputs and selectors.

### Semantic Status Pairings (WCAG 2.1 AA Verified)
All status badges and callouts must use paired foreground and soft background tokens:
- **Success (`#2f7d32` on `#edf7ed`)**: Passing criteria, verified curricula, compliant status (4.66:1 contrast).
- **Info (`#1f718f` on `#eaf7fb`)**: Informational notices, document metadata, reference indicators (5.03:1 contrast).
- **Warning (`#8a5a00` on `#fff7db`)**: Incomplete criteria, partial-mode notices, review reminders (5.53:1 contrast).
- **Destructive (`#b42318` on `#fff0ee`)**: Failed evaluations, non-compliant criteria, critical deletion warnings (5.93:1 contrast).

---

## Typography

EquipED uses **Public Sans**—an open-source, civic typeface created by the United States Web Design System (USWDS)—self-hosted locally for data privacy and zero external network calls.

### Typographic Roles
- **Display (`32px / 700 / -0.02em / lh 1.15`)**: Evaluation score overview headers and landing metrics.
- **Heading LG (`28px / 700 / -0.015em / lh 1.25`)**: Screen page titles (e.g., "Evaluation Setup", "Document Dashboard").
- **Heading MD (`20px / 600 / -0.01em / lh 1.35`)**: Major section dividers, card ledger headers, modal titles.
- **Heading SM (`16px / 600 / normal / lh 1.4`)**: Sub-sections, form groups, criterion domain labels.
- **Body MD (`15px / 400 / normal / lh 1.6`)**: Reading canvas narratives, evaluation reasoning, and rubric descriptors. Maximum reading measure is constrained to 65–75 characters.
- **Body SM (`14px / 500 / normal / lh 1.4`)**: Interactive controls, buttons, input text, and table body data.
- **Label SM (`12px / 600 / 0.04em / lh 1.4`)**: Form labels, status badge text, table column headers. Defaults to sentence case; uppercase is restricted to formal academic codes (e.g., "BSCS", "ITSO").
- **Data MD (`13px / 500 / normal / lh 1.35`)**: Scores, weights, percentages, timestamps, and matrix rows. Must render with `font-variant-numeric: tabular-nums` for precise vertical decimal alignment.

---

## Layout & Page Archetypes

Layouts reflect an authentic academic ledger workspace structured around two definitive page archetypes:

### Archetype A: The Overview Ledger (Full-Width Containerized)
Applied to: Dashboard (`/dashboard`), SLM Storage Repository (`/documents`), User Management, Monitoring Matrix.
* **Container Constraint**: `max-w-[108rem] (1728px)` with horizontal auto-margins (`mx-auto px-4 sm:px-6 py-6`).
* **Grid Discipline**: Strict 12-column grid or responsive 4-column cards (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`).
* **Anti-Empty Margin Rule**: Elements must span their full container width with balanced internal data density. Never center narrow `max-w-3xl` columns on expansive desktop screens leaving wide empty canvas margins.
* **Structural Layer Sequencing**:
  1. Workstation Hero Header (Heading LG title, primary eyebrow, primary action CTA)
  2. Repository Pulse / Metrics Strip (Full width, dense tabular numbers, semantic status icons)
  3. Workstation Launchpads or Filter Toolbars
  4. Primary Tabular Ledger (Sticky headers, compact rows, right-aligned data)

### Archetype B: The Inspection Workstation (Split-Pane, Full-Height)
Applied to: Specialist Scoreboards (`/specialists/$agentId/$documentId`), Syllabus Alignment Workspace, Evaluation Scorecards.
* **Viewport Constraint**: Full viewport height `min-h-[calc(100vh-4rem)] flex flex-col bg-canvas`.
* **Pane Distribution**:
  - **Left Pane (Reference Dossier)**: Fixed width (`22rem` to `28rem`), border-right separator (`border-r border-border`), dedicated scroll container (`overflow-y-auto p-4 sm:p-5`). Houses read-only reference facts (metadata matrix, unit outline).
  - **Right Pane (Action Docket / Scoreboard)**: Fluid width (`flex-1 min-w-0`), independent scroll container (`overflow-y-auto p-6 sm:p-8`). Houses interactive criteria, domain tabs, and authoritative review actions.
* **Responsive Collapse**: Screens below `1024px` (`lg`) stack panes sequentially with tabbed navigation.

---

## Spacing Architecture (Macro vs. Micro Rhythm)

EquipED structures spatial intervals around a 4px base unit grouped into three functional tiers:

* **Micro Spacing (`4px`–`8px`)**:
  - `4px` (`gap-1`, `space-y-1`): Micro badge padding, inline icon gaps, tabular suffix offsets.
  - `8px` (`gap-2`, `space-y-2`): Form label to control offset (`mb-1.5`), list item separation in drawers, metadata key-value row spacing.
* **Component Padding (`16px`–`24px`)**:
  - `16px` (`p-4` / `p-4.5`): Standard interior padding for ledger cards, compact dossiers, and table headers.
  - `24px` (`p-6`): Primary workstation cards, modal interiors, and dashboard containers.
  - *Anti-Pattern*: Do not apply arbitrary padding (e.g. `p-12` or `p-2`) to standard ledger containers.
* **Macro Spacing & Section Rhythm (`24px`–`32px`)**:
  - `24px` (`space-y-6`): Standard vertical interval separating screen zones (Header → Metrics Strip → Launchpads → Ledger).
  - `32px` (`space-y-8`): Dedicated section margins in complex configuration flows.

## Elevation, Depth & Tonal Layering

EquipED employs a **flat-by-default** elevation model. Depth is established through intentional tonal recession and layered borders rather than floating drop shadows:

### The 3-Plane Tonal Depth Model
* **Plane 0 (Canvas Backdrop `#f4f7fb`)**: The cool institutional foundation separating panels.
* **Plane 1 (Surface Sheets `#ffffff`)**: Primary ledger cards and tables bounded by crisp 1px borders (`#d6deea`).
* **Plane 2 (Recessed Sunken Trays `#f8fafc` / `#edf2ff`)**: Embedded trays inside cards for key-value ledgers, filter toolbars, and metadata blocks (`bg-surface-subtle p-3.5 rounded-sm`), creating physical depth without drop shadows.

### 3-Tier Border Hierarchy
* **Structural Border (`#d6deea`)**: 1px outer perimeters of cards, split-pane dividers, primary table edges.
* **Interior Hairlines (`#d6deea` at 50%–60% opacity / `#e2e8f0`)**: Subtle separation inside cards and between compact key-value pairs, eliminating harsh heavy lines.
* **Interactive Focus / Hover Border (`#1b3b87` at 40%–60%)**: Subtle brand glow when hovering over actionable workstation cards or active tabs.

### Modals & Interactive Focus
* **Modals & Dialogs**: Centered over a dimmed backdrop (`rgba(15, 23, 42, 0.45)`) with a subtle 1px border and minimal functional shadow (`0 4px 12px rgba(15, 23, 42, 0.08)`). Large blurred halos (blur > 16px) are forbidden.
* **State-Only Focus**: Active interactive elements display a 2px royal blue outline (`ring-2 ring-[#1b3b87]`) with a 1px offset.
---

## Shapes

Shapes prioritize structural discipline:
- **Border Radius**: Strictly capped between `0px` and `6px`.
  - `0px` (`none`): Table headers, split-pane dividers, full-width canvas panels.
  - `2px` (`xs`): Checkboxes, micro status chips, tabular data badges.
  - `4px` (`sm`): Buttons, text inputs, dropdown triggers, search bars.
  - `6px` (`md`): Primary cards, floating modal windows, dialog containers.
- **No Circular Bubbles**: Pill buttons and large capsule tags are prohibited for primary controls.

---

## Components

### Buttons
- **Primary**: Solid LSPU Royal Blue (`#1b3b87`), white text, 4px radius, 40px standard height (`h-10 px-4`). Focus: 2px offset ring.
- **Secondary**: White surface, 1px border (`#d6deea`), slate text (`#172033`). Hover: subtle slate tint (`#f8fafc`).
- **Destructive**: Solid Red (`#b42318`), white text, 4px radius. Used exclusively for permanent actions (deleting document, canceling active run).

### Form Controls
- **Text Inputs & Selects**: 40px height (`h-10`), 1px border (`#c8d2e1`), white surface, 4px radius, 12px horizontal padding.
- **Labels**: Rendered above inputs in sentence case using `label-sm` (`12px`, semibold, `#172033`).
- **Hint Text**: Rendered below inputs using `#596579` (`12px`).

### Status Badges
- Compact rectangular chips with 2px radius and 1px borders.
- Always combine a foreground text color, a soft tinted background, and an icon or explicit label (never rely on color alone).

### Tables & Ledgers
- Table headers use `surface-subtle` (`#f8fafc`), 1px bottom border, and semibold sentence-case labels.
- Rows use 1px horizontal dividers (`divide-y divide-[#d6deea]`).
- Hover states on interactive rows apply a subtle tint (`hover:bg-[#f8fafc]`).
- Scores and numbers use `data-md` with tabular numbers enabled.

---

## Do's and Don'ts

### Do:
- **Do** use crisp 1px borders (`#d6deea`) to structure cards, split panes, and tables.
- **Do** maintain a strict line-height of 1.6 on evaluation prose and comments for long-term readability.
- **Do** enable `tabular-nums` on all numbers, scores, weights, and dates.
- **Do** respect the 6px maximum border-radius limit across all UI components.
- **Do** pair all status indicators with descriptive text and icons for accessibility.
- **Do** keep button and form interactive heights at a minimum of 40px for touch and click precision.

### Don't:
- **Don't** use purple, violet, or blue-purple gradient meshes anywhere in the application.
- **Don't** apply floating card shadows (blur > 16px) or glassmorphic blur filters.
- **Don't** use pure black (`#000000`) for text or backgrounds; use `#172033` and `#f4f7fb`.
- **Don't** render SCC Amber Gold (`#f2c811`) text on white or light backgrounds.
- **Don't** use ALL-CAPS text for long headings, table cell values, or paragraphs.
- **Don't** use decorative animations or micro-bounces that delay faculty access to evaluation data.
