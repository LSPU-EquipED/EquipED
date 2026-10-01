---
version: alpha
name: EquipED
description: Institutional SLM evaluation workbench for LSPU faculty and CID reviewers

colors:
  primary: "#1b3b87"
  primary-strong: "#142f70"
  primary-soft: "#e8eef9"
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
  ring: "#1b3b87"

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

The interface uses a cool blue-gray canvas, ink-colored typography, compact controls, and clear structural borders. Royal blue is the action color; amber is reserved for review attention and institutional emphasis. The product should never depend on gradients, glass effects, decorative blobs, or stacked floating cards to create hierarchy.

## Foundations

### Color

- **Canvas** `#eef2f3` is the page background.
- **Surface** `#fbfcfc` is used for panels, tables, and the reading workspace.
- **Surface subtle** `#e7edef` supports quiet grouping and loading states.
- **Primary** `#1b3b87` is the royal blue used for links, active navigation, and primary actions.
- **Primary strong** `#142f70` is for hover, pressed, and high-emphasis states.
- **Primary soft** `#e8eef9` supports selected items and quiet primary backgrounds.
- **Focus ring** `#1b3b87` keeps keyboard focus aligned with the royal blue action palette.
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
- The top bar carries breadcrumbs, the mobile menu control, and the account control. The account control is a compact circular initials avatar, with the shared primary-soft fill and a visible focus ring.
- Sidebar navigation is grouped by responsibility. Group labels use sentence case, 11px text, and modest tracking. Active items use primary-soft, primary text, and a clear leading rule.
- Keep navigation labels short and descriptive. Faculty uses `Dashboard`, `Module Library`, `SME Specialist`, `Program Coordinator`, `GAD Specialist`, `ITSO Specialist`, `Syllabus`, `Curriculum`, and `Evaluation History`. Admin retains its descriptive operational labels. Sidebar groups remain organized by responsibility, and breadcrumbs use the same names as their navigation items.

## Page composition

### Faculty dashboard

The first viewport should answer: what needs attention, what is active, and what can I do next? Place a full-width greeting and compact KPI row above an asymmetrical desktop grid with a wide main column and a compact 18–22rem supporting column:

1. A full-width personal, time-aware greeting with the local date. Keep the banner compact and focused on the greeting. Use a restrained module-and-review illustration on larger screens and the primary-soft surface.
2. Four compact KPI cards beneath the greeting: total modules, processed, processing, and failed uploads. Use four columns on desktop and two on mobile, with the label and a modest value side by side. Processing counts describe document intake, not evaluation completion; keep values and labels close in size and omit explanatory subtitles.
3. A conditional current-evaluation panel beside the activity table with the actual specialist, server-reported stage, module title, and a direct progress link. A compact stage sequence provides context without percentages or time estimates. Avoid internal IDs, spinners, and repeated status badges.
4. Recent activity occupies the wide column with evaluation/review tabs, search, refresh, and pagination; keep a compact quick-actions panel in the supporting column, beneath current progress when an evaluation is active. Use spacing beneath the KPI row, and separate the desktop workspace columns with a vertical rule centered in the gutter. Place an Evaluation activity heading above the table surface, matching the quick-action group headings. The table footer contains only pagination and page-size controls; evaluation history remains in the sidebar. Stack the greeting, summary, active evaluation, quick actions, and activity on smaller screens, keeping table scrolling inside its panel.

Quick actions are grouped by purpose: an Evaluation workspaces group filtered to permitted specialists, and an Alignment checks group. Each group has a sentence-case heading above a lightly bordered surface with thin row separators. Give rows 20px vertical padding, relaxed description line height, and 28px between groups; widen the supporting column on larger desktops without squeezing the table at smaller widths. Rows use consistent bordered icon tiles, semibold labels, and diagonal arrows. Specialist rows include one brief purpose description; alignment rows contain only their label. Uploads remain available in Module Library; do not add an upload shortcut to the dashboard. Do not duplicate the history shortcut. Omit generic advisory notices from the dashboard; retain guidance where users review and act on generated findings. Keep the greeting visible when workspace data is loading or fails, and show loading counts rather than invented zeroes.

Keep the faculty dashboard flat and compact: lightly bordered surface panels, simple KPI cards, soft-fill activity tabs, and restrained typography. Preserve the desktop column divider; use spacing without a horizontal rule beneath the KPI cards. Depth comes from the layered banner illustration rather than panel shadows; avoid the expanded administrative overview-list treatment.

### Admin user management

Keep each row's actions behind a single three-dot button that opens a compact, keyboard-accessible menu. Use existing control and dropdown tokens, keep the menu clear of table clipping, and separate permanent deletion from routine commands. The deletion dialog requires the account's email and keeps confirmation disabled until it matches. The signed-in administrator's account is excluded from the directory and bulk selection.

### Visual anchors for low-data states

Whitespace should clarify the workflow, not look unfinished. When a page has no records, few records, or a quiet secondary rail, use a restrained diagrammatic visual that explains the evidence path: module, review, decision. Prefer thin connectors, document or rubric glyphs, and existing semantic colors over decorative illustrations, gradients, or unrelated imagery. These anchors should disappear or recede once operational content takes over the viewport.

### Review and inspection

Specialist launchpad whitespace should use a compact scorecard preview instead of a decorative illustration. Show the evidence layers that will be produced—source excerpts, rubric criteria, and the review record—with quiet bars and document glyphs. Keep the visual inside the launch surface, secondary to the action, and light enough to preserve the institutional surface language.

When a specialist queue is clear, let the workstation occupy the available viewport height. Use a small queue snapshot inside the empty state to make the space operationally useful; do not place a separate illustration below the workstation.

Evaluation screens should privilege the document, criterion, and reviewer decision. Use split panes or clear sequential sections, persistent context, and explicit advisory labels for generated guidance. Human review remains authoritative.

Specialist results use a criteria-first layout: one module title and action toolbar, a narrow left metadata rail, and a compact score/rating strip above the criteria. Keep the specialist summary and record IDs behind disclosures. Criteria begin collapsed as compact rows, with evidence warnings and reviewer corrections visible before expansion. On smaller screens, metadata is collapsed instead of stacking a full panel above the scorecard. Avoid repeated metadata, nested cards, and large introductory headers; several criteria should be visible in the first desktop viewport.

### Admin operations

Admin pages are dense operational tools: tables, filters, status summaries, and focused forms. Preserve the same shell and tokens as Faculty; vary hierarchy through content and layout, not a second visual language.

Training Data uses wide specialist tabs followed by dataset preparation, a conditional notebook handoff, run history, and uploaded adapters. Place the preparation action beside readiness; preparing a run freezes a dataset and issues notebook URLs rather than launching training. Keep seeded-data and reviewer limitations visible, with inclusion details behind a disclosure. Use compact counts and sentence-case section headings instead of repeated card headers. History rows prioritize dates, dataset size, and recorded state, with full identifiers and hashes available in expandable details. Adapter receipt does not imply validation or activation. Preserve unsaved notebook URLs in page memory across specialist changes and require acknowledgment before replacing them; do not persist these credentials in browser storage.

Group dataset preparation in one framed tool, with readiness, compact label/value count rows, and the preparation action on the left and a quiet dataset-notes area on the right. Use a structural divider between these areas and stack them on smaller screens. Keep the conditional notebook handoff close to preparation, with separate full-width download and upload rows; each row groups its label, notebook-cell hint, URL, copy action, and expiry. Records remain full-width with consistent headings and counts; show dates in the main rows and timestamps in expanded details. Adapter server setup instructions belong in expanded details, never in the status cell. Empty records explain the next workflow step, and loading placeholders match the final table geometry.

Run history and uploaded adapters show five records per page by default. Lists longer than five records have independent compact footers with a record range, previous/next controls, and the shared rows-per-page dropdown (5, 10, or 20). Reset to the first page when changing the page size or specialist, and keep the current page within the available range when records refresh.

## Component rules

- Primary buttons use primary fill, white text, a 2-4px radius, and a visible pressed state.
- Secondary buttons use a surface fill with a border. Icon-only controls require an accessible label and tooltip.
- Inputs, selects, and tabs share the 40px control height and use the input border token.
- Tables use strong column alignment, compact rows, sticky context only when it improves review, and tabular numerals for data.
- Status badges pair a semantic color with text and an icon or label. Do not rely on hue alone.
- Empty, loading, error, and partial states are first-class layouts with clear next actions. Loading states use geometry-matched skeletons that preserve the final layout; do not use freestanding loading spinners.
- Active evaluations show their server-reported stage (queued, preparation, specialist review, finalizing) with visible progress context and the selected specialist. Reserve skeletons for fetching workspace data or completed results; do not replace a running evaluation with placeholders or invent completion percentages and time estimates.

## Motion and accessibility

Motion is short and functional: 120ms micro interactions, 180ms compact transitions, and 240ms surface transitions. Respect `prefers-reduced-motion`. Preserve visible focus rings, keyboard navigation, semantic landmarks, and sufficient contrast. Mobile drawers must manage focus and expose their open state to assistive technology.

## Product content

Use direct, institutional language. Say what is ready, what is blocked, and who owns the next decision. Generated evaluations and recommendations are advisory; reviewer decisions and ownership boundaries are authoritative. Keep data local and avoid exposing SLM content outside configured institutional workflows.

## Do and do not

**Do:** use sentence case, evidence-led hierarchy, compact controls, structural borders, clear status text, and generous breathing room around important review decisions.

**Do not:** introduce gradients, glassmorphism, oversized hero typography, decorative avatar effects, dense uppercase navigation, unrelated color themes, or nested card stacks.
