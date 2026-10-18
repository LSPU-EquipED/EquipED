# Specialist workspace illustration concepts

The user selected **02 — Paper and evidence** as the original visual direction.
The first concept remains an unimported exploration. The first expanded family
was rejected for repeating the same manuscript silhouette. That family and its
motion are archived under `superseded/`; `asset-prompts.json` is its historical
generation record (and retains the background study's prompt).

The current family uses different subjects with a shared palette and editorial
linework:

- Four large PNG illustration studies in `raster-studies/`.
- A folded-paper background in `workspace-folds.png`.
- Four editable SVG state assets in `../../animations/workspace/`.

`distinct-asset-prompts.json` records the built-in image-generation prompts for
the current PNG family: inspection desk, curriculum drafting board, inclusive
discussion, and invention prototype. The SVGs are hand-authored, not raster
images embedded in SVG files.

Generated with the built-in image-generation tool for visual selection before
changing the specialist workspace layout. Full prompts are in `prompts.json`.

- `01-annotated-folio.png`: layered manuscript, highlighted excerpt, annotation
  slips, and a pen; softer paper depth.
- `02-paper-and-evidence.png`: outlined manuscript and reference slips with a
  folded blue ribbon; more graphic composition.

Both files are 1536 × 1024 RGBA PNGs with transparent outer pixels. Their
semi-transparent shading is part of the generated artwork. These are raster
explorations, not editable vectors or finished animated assets. Neither is
imported by the application.

The SVG states now have different compositions: a waiting tray and clock,
assembly frame with moving pages, travelling inspection lens, and findings
folder. Motion loops within each state, with pause/resume controls in the specialist workspace. Reduced-motion preferences show static artwork. The production layouts and existing dashboard assets are intact.

The generated optical-desk, curriculum-board, discussion, and prototype PNGs
are retained under `raster-studies/`. The current workspace uses native SVG
interpretations of these subjects, aligned with the flat Folio identity.
