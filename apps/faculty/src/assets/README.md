# Shared faculty assets

This folder owns artwork shared across faculty features, reusable surface textures,
and archived design explorations. Feature-specific assets live with their feature.
Shared EquipED logos, the LSPU emblem, and Public Sans fonts remain in
`libs/ui/src/assets/`.

## Shared runtime assets

- `illustrations/syllabus-check.svg`: used by the dashboard alignment
  shortcut and the Syllabus check page.
- `illustrations/curriculum-check.svg`: used by the dashboard alignment
  shortcut and Curriculum check controls.
- `textures/paper-grain.svg`: reusable 48px surface texture, currently used by the
  dashboard stylesheet.

Keep assets used by multiple features here so features do not import from one
another. Keep single-feature artwork in the owning feature's `assets/` directory,
grouped by component purpose. Update existing references when promoting or moving
an asset; do not duplicate the same artwork across features.

## Feature-owned collections

- [`../features/home/assets/`](../features/home/assets/README.md): welcome banner,
  module overview, and dashboard specialist illustrations.
- [`../features/evaluation/assets/workspace/`](../features/evaluation/assets/workspace/README.md):
  specialist landing scenes, setup/recovery illustrations, and evaluation motion.
- `../features/evaluation/assets/pdf-templates/`: the four institutional specialist
  export templates and their measured layouts.

Finished SVGs use transparent backgrounds, explicit view boxes, and the royal
blue, paper, neutral, and amber palette. They require no fonts or external
resources. Their colors remain self-contained for rendering outside the app.
Interface text conveys meaning; decorative artwork uses empty alternative text.

## Exploration archive

Explorations remain part of the asset collection and are not imported by runtime
code. Preserve their generation prompts alongside them.

- `explorations/faculty-dashboard/`: earlier generated illustrations, abstract
  folds, banner background, icon concepts, and texture studies. The icon sheet
  contains shading/background pixels and the raster texture has unverified repeat
  seams; the dashboard uses finished SVGs instead.
- `explorations/specialist-workspace/`: the original paper-and-annotation concepts,
  distinct raster studies, and the unused `workspace-folds.png` background study.
  Rejected repetitive artwork and motion remain under `superseded/`. The selected
  second direction informed the current feature-owned vector family.
