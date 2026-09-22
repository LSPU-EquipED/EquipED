---
version: alpha
name: EquipED
description: Institutional SLM evaluation workbench for LSPU faculty and CID reviewers

colors:
  primary: "#16445d"
  primary-strong: "#0d3044"
  primary-soft: "#e4eff3"
  primary-foreground: "#ffffff"
  secondary: "#d9ad1d"
  secondary-foreground: "#1b2b33"
  accent: "#d9ad1d"
  accent-soft: "#fbf3cf"
  accent-foreground: "#493b08"
  success: "#28754b"
  success-soft: "#e8f3ec"
  success-foreground: "#ffffff"
  info: "#28758a"
  info-soft: "#e4f1f4"
  info-foreground: "#ffffff"
  warning: "#86620a"
  warning-soft: "#fbf3d9"
  warning-foreground: "#ffffff"
  destructive: "#b13b32"
  destructive-soft: "#fbeceb"
  destructive-foreground: "#ffffff"
  canvas: "#eef2f3"
  surface: "#fbfcfc"
  surface-subtle: "#e7edef"
  text: "#1b2b33"
  text-muted: "#60717a"
  border: "#cad6da"
  border-strong: "#91a5ad"
  input: "#b7c7cc"
  ring: "#28758a"

typography:
  family: "Public Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
  tracking: normal
  body: "15px / 1.6"
  label: "12px / 1.4 / 600"
  data: "13px / 1.35 / 500"

spacing:
  unit: 4px
  control: 40px
  topbar: 56px
  sidebar: 256px
  sidebar-collapsed: 72px

rounded:
  none: 0px
  sm: 2px
  md: 4px
  lg: 6px
---

# EquipED Design System

## Direction

**Institutional Workbench** is the visual direction for EquipED: a calm, evidence-first workspace for evaluating Self-Paced Learning Modules (SLMs). It should feel dependable during long review sessions, closer to a well-made academic records system than a marketing dashboard.

The interface uses a cool blue-gray canvas, ink-colored typography, compact controls, and clear structural borders. LSPU teal is the action color; amber is reserved for review attention and institutional emphasis. The product should never depend on gradients, glass effects, decorative blobs, or stacked floating cards to create hierarchy.

## Foundations

### Color

- **Canvas** `#eef2f3` is the page background.
- **Surface** `#fbfcfc` is used for panels, tables, and the reading workspace.
- **Surface subtle** `#e7edef` supports quiet grouping and loading states.
- **Primary** `#16445d` is for links, active navigation, and primary actions.
- **Primary strong** `#0d3044` is for pressed and high-emphasis states.
- **Amber** `#d9ad1d` is for review attention, not general decoration.
- **Text** `#1b2b33` and **text muted** `#60717a` provide the reading hierarchy.
- Semantic colors use their matching soft background tokens. Status must never be conveyed by color alone.

### Type

Use Public Sans throughout the product. Headings are sentence case, compact, and left aligned. Letter spacing is normal; do not use negative tracking or all-caps labels to manufacture hierarchy. Use tabular numerals for scores, counts, dates, and evaluation IDs.

### Shape and spacing

Use a 4px spacing unit and restrained 0-6px radii. Controls are normally 40px tall. Borders are structural: use one-pixel separators and modest contrast instead of heavy shadows. Cards are reserved for genuinely framed tools, repeated records, and dialogs; page sections should remain full-width and unframed.

## Application shell

- The desktop top bar is 56px tall and uses the canvas color with a bottom border.
- The desktop sidebar is 256px wide; the collapsed rail is 72px wide. Mobile uses a drawer.
- Main content uses the canvas background and begins below the top bar and beside the sidebar.
- The top bar carries breadcrumbs, the mobile menu control, and the account control. The account control is a compact square workbench affordance, not a decorative avatar bubble.
- Sidebar navigation is grouped by responsibility. Group labels use sentence case, 11px text, and modest tracking. Active items use primary-soft, primary text, and a clear leading rule.
- Keep navigation labels short and operational: `Home`, `Documents`, `Evaluations`, `Curriculum`, and `Logs` in Faculty; `Overview`, `Operations`, `Knowledge base`, and `Model governance` in Admin.

## Page composition

### Faculty overview

The first viewport should answer: what needs attention, what is active, and what can I do next? Use this order:

1. Page heading and top-level context with operational upload affordances available directly within primary workflows (such as the SLM Storage toolbar action).
2. Compact metrics for owned modules and evaluation state.
3. Active evaluation or attention-required work.
4. Recent evaluation activity and a link to the full history.
5. Secondary tools only after the operational content.

Avoid a grid of identical metric cards. Give the active workflow the strongest visual weight and keep the activity ledger scannable.

### Visual anchors for low-data states

Whitespace should clarify the workflow, not look unfinished. When a page has no records, few records, or a quiet secondary rail, use a restrained diagrammatic visual that explains the evidence path: module, review, decision. Prefer thin connectors, document or rubric glyphs, and existing semantic colors over decorative illustrations, gradients, or unrelated imagery. These anchors should disappear or recede once operational content takes over the viewport.

### Review and inspection

Specialist launchpad whitespace should use a compact scorecard preview instead of a decorative illustration. Show the evidence layers that will be produced—source excerpts, rubric criteria, and the review record—with quiet bars and document glyphs. Keep the visual inside the launch surface, secondary to the action, and light enough to preserve the institutional surface language.

When a specialist queue is clear, let the workstation occupy the available viewport height. Use a small queue snapshot inside the empty state to make the space operationally useful; do not place a separate illustration below the workstation.

Evaluation screens should privilege the document, criterion, and reviewer decision. Use split panes or clear sequential sections, persistent context, and explicit advisory labels for generated guidance. Human review remains authoritative.

Specialist results use a criteria-first layout: one module title and action toolbar, a narrow left metadata rail, and a compact score/rating strip above the criteria. Keep the specialist summary and record IDs behind disclosures. Criteria begin collapsed as compact rows, with evidence warnings and reviewer corrections visible before expansion. On smaller screens, metadata is collapsed instead of stacking a full panel above the scorecard. Avoid repeated metadata, nested cards, and large introductory headers; several criteria should be visible in the first desktop viewport.

### Admin operations

Admin pages are dense operational tools: tables, filters, status summaries, and focused forms. Preserve the same shell and tokens as Faculty; vary hierarchy through content and layout, not a second visual language.

## Component rules

- Primary buttons use primary fill, white text, a 2-4px radius, and a visible pressed state.
- Secondary buttons use a surface fill with a border. Icon-only controls require an accessible label and tooltip.
- Inputs, selects, and tabs share the 40px control height and use the input border token.
- Tables use strong column alignment, compact rows, sticky context only when it improves review, and tabular numerals for data.
- Status badges pair a semantic color with text and an icon or label. Do not rely on hue alone.
- Empty, loading, error, and partial states are first-class layouts with clear next actions. Loading states use geometry-matched skeletons that preserve the final layout; do not use freestanding loading spinners.

## Motion and accessibility

Motion is short and functional: 120ms micro interactions, 180ms compact transitions, and 240ms surface transitions. Respect `prefers-reduced-motion`. Preserve visible focus rings, keyboard navigation, semantic landmarks, and sufficient contrast. Mobile drawers must manage focus and expose their open state to assistive technology.

## Product content

Use direct, institutional language. Say what is ready, what is blocked, and who owns the next decision. Generated evaluations and recommendations are advisory; reviewer decisions and ownership boundaries are authoritative. Keep data local and avoid exposing SLM content outside configured institutional workflows.

## Do and do not

**Do:** use sentence case, evidence-led hierarchy, compact controls, structural borders, clear status text, and generous breathing room around important review decisions.

**Do not:** introduce gradients, glassmorphism, oversized hero typography, circular avatar decoration, dense uppercase navigation, unrelated color themes, or nested card stacks.
