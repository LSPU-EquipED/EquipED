---
name: EquipED
description: Academic SLM Evaluation Workspace
colors:
  primary: "#1b3b87"
  primary-foreground: "#ffffff"
  secondary: "#f2c811"
  secondary-foreground: "#1e293b"
  success: "#3b963e"
  success-foreground: "#ffffff"
  info: "#3eaed4"
  destructive: "#b91c1c"
  neutral-bg: "#ffffff"
  neutral-fg: "#1e293b"
  border: "#e2e8f0"
  muted: "#f8fafc"
  muted-foreground: "#64748b"
typography:
  display:
    fontFamily: "Inter, sans-serif"
    fontSize: "clamp(1.75rem, 4vw, 2.5rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Inter, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.05em"
rounded:
  sm: "4px"
  md: "6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-foreground}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  card-container:
    backgroundColor: "{colors.neutral-bg}"
    rounded: "{rounded.sm}"
    padding: "16px"
---

# Design System: EquipED

## 1. Overview

**Creative North Star: "The Faculty Ledger"**

EquipED is designed as an institutional review workstation for Laguna State Polytechnic University faculty members. The visual metaphor, "The Faculty Ledger," prioritizes high clarity, academic structure, and immediate verification of SLM automated evaluations. All screens feature high-density layouts, grid-structured table cells, and simple English descriptions to minimize cognitive load during compliance analysis.

By centering on the ledger metaphor, EquipED rejects the SaaS-cliché aesthetic of spacious margins, floaty card components, and soft drop shadows. Instead, it utilizes tight line spacing, crisp borders, and a royal blue and amber gold institutional identity.

**Key Characteristics:**
- **Academic Ledger Grid**: Clear boundaries, tabular layouts, and 1px high-contrast borders instead of layered panels.
- **Expert Density**: Compact side-by-side split screens showing original document segments alongside detailed evaluation scorecards.
- **Simple, Direct English**: Advisory copy that clearly states the status and reasoning behind LLM flags.

## 2. Colors

The color palette is derived directly from the Laguna State Polytechnic University (LSPU) official logo, capturing the academic quadrants (Agriculture, Fisheries, Technology, and Education) and institutional blue/gold framing.

### Primary
- **LSPU Royal Blue** (#1b3b87 / oklch(0.32 0.15 260)): Taken from the outer circular brand ring. Used for structural headers, primary actions, and primary navigation focus. It commands authority and highlights institutional alignment.

### Secondary
- **SCC Amber Gold** (#f2c811 / oklch(0.81 0.17 85)): Taken from the central open book. Used for high-contrast alerts, warning flags, and highlights.
- **Verification Green** (#3b963e / oklch(0.58 0.16 140)): Taken from the agriculture leaf quadrant. Used to indicate passing status, verified sections, and positive compliant metrics.
- **Fisheries Cyan** (#3eaed4 / oklch(0.69 0.15 220)): Taken from the fisheries fish quadrant. Used for informative status states, tooltips, and relative reference links.
- **Technology Brown** (#704022 / oklch(0.38 0.11 50)): Taken from the technology gear quadrant. Used for muted background panels and stable academic grids.

### Neutral
- **Academic White** (#ffffff / oklch(1 0 0)): The canvas background for all tables and document panels to maintain readability.
- **Slate Page BG** (#f8fafc / oklch(0.98 0.005 240)): Clean, slightly cool neutral-gray page background. Warm cream, parchment, sand, or beige backgrounds are explicitly banned to prevent generic AI slop.
- **Slate Text** (#1e293b / oklch(0.22 0.02 240)): High-contrast body text to prevent eye fatigue.
- **Slate Muted** (#64748b / oklch(0.48 0.02 240)): Secondary metadata labels and auxiliary table info.
- **Grid Border** (#e2e8f0 / oklch(0.92 0.01 240)): Crisp lines separating columns, rows, and panels.

### Named Rules
**The Rare Accent Rule.** Accent colors (LSPU Royal Blue and SCC Amber Gold) are restricted to ≤10% of any view. Their rarity ensures that faculty focus is drawn only to active buttons and active compliance violations.
**The High Contrast Rule.** No text or status label may fall below a 4.5:1 contrast ratio against its background. Light gray captions on white backgrounds are strictly forbidden.
**The Basic English Rule.** All headers, labels, buttons, and helper texts must use basic, direct English. Avoid overly clinical, academic, or pretentious terms (e.g. use "Sign In" instead of "System Authorization" or "Access Ledger").

## 3. Typography

**Display Font:** Inter, sans-serif (system-ui fallback)
**Body Font:** Inter, sans-serif (system-ui fallback)
**Label/Mono Font:** Inter, sans-serif (system-ui fallback)

The typography layout uses Inter with strict scale constraints to maintain legibility. Display headlines are tight and clean with minimal letter-spacing.

### Hierarchy
- **Display** (Bold (700), clamp(1.75rem, 4vw, 2.5rem), 1.2): Main page headers and high-level evaluation summaries.
- **Headline** (Semi-Bold (600), 1.5rem, 1.3): Major section dividers and card groups.
- **Title** (Semi-Bold (600), 1.25rem, 1.4): Table headers, category labels, and card titles.
- **Body** (Regular (400), 0.9375rem, 1.6): Standard evaluation reasoning, code blocks, and rubric text. Max line length is kept under 75ch.
- **Label** (Medium (500), 0.75rem, 1.4, Uppercase with 0.05em tracking): Small meta-text labels, status badges, and table column headers.

### Named Rules
**The Readable Prose Rule.** All paragraphs presenting evaluation comments or criteria rubrics must maintain a line-height of 1.6 to prevent lines from blending during long grading sessions.

## 4. Elevation

The elevation system is strictly flat. We reject drop shadows, card float animations, and layered window stacks to align with the "Faculty Ledger" metaphor.

### Named Rules
**The Flat-By-Default Rule.** All containers, inputs, and buttons are flat against the background at rest. Depth is established exclusively through 1px border lines and distinct background value changes (Academic White vs. slate gray panels).
**State-Only Focus Rule.** Subtle borders or ring outline changes are allowed only in response to focus states (e.g. keyboard focus or text selection).

## 5. Components

All components are designed to feel integrated, solid, and grid-aligned.

### Buttons
- **Shape:** Minimal radius (4px) or completely square.
- **Primary:** LSPU Royal Blue background with Academic White text. Medium padding (6px 12px).
- **Secondary:** SCC Amber Gold background with Academic White text.
- **Hover / Focus:** 10% dark overlay on hover (`filter: brightness(0.9)`), with a 2px blue ring focus offset.

### Cards / Containers
- **Corner Style:** Flat or slightly curved (4px or 6px radius).
- **Background:** Academic White.
- **Border:** 1px solid Slate Grid Border.
- **Internal Padding:** 16px.

### Inputs / Fields
- **Style:** 1px Slate Grid Border stroke, white background, 4px radius.
- **Focus:** 2px LSPU Royal Blue outline.
- **Error:** 1px Destructive Red border (#b91c1c) with a light red background tint.

### Navigation
- **Style:** Compact vertical list or top tab bar. Active links use a solid 2px LSPU Royal Blue underline or left boundary line.

## 6. Do's and Don'ts

### Do:
- **Do** use crisp 1px borders (#e2e8f0) to separate the main evaluation sections from the uploaded document preview.
- **Do** ensure all automated evaluations and domain rubrics are displayed in clear, plain English.
- **Do** restrict rounded corners to a maximum of 6px to preserve the academic ledger aesthetic.

### Don't:
- **Don't** use generic SaaS floating cards with soft, wide drop shadows (e.g., box-shadow blur ≥ 16px).
- **Don't** use decorative gradient text or stripes.
- **Don't** use external shadcn/ui or tailwind-scaffold template elements without custom branding.
- **Don't** hide evaluation logic or raw weights behind tooltips or collapsed tabs; all rationales must be readable.
