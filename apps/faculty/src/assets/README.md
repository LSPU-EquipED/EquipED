# Faculty assets

Faculty-only visual assets live here, independent of feature implementation.
Shared EquipED logos remain under `libs/ui/src/assets/brand/`.

## Organization

- `backgrounds/`: finished compositions used behind interface content.
- `illustrations/`: standalone artwork, with specialist and alignment families in
  `specialists/` and `alignment/`.
- `textures/`: repeatable surface patterns.
- `explorations/faculty-dashboard/`: dashboard concepts and their generation prompts.

Keep finished assets grouped by type rather than by the feature using them.
Explorations remain part of the asset collection and are not imported by runtime code.

## Finished SVGs

These are hand-authored vectors with transparent backgrounds, explicit view boxes,
and the current royal blue, paper, neutral, and amber brand palette. They require
no fonts or external resources.

- `backgrounds/welcome-folds.svg`: scalable folded-paper composition for the greeting panel.
- `textures/paper-grain.svg`: seamless 48px repeating micro-pattern for quiet surface texture.
- `illustrations/module-collection.svg`: folder-and-module collection for the library tile, designed for a 144–192px display width.
- `illustrations/specialists/`: coherent specialist illustrations, used at 56–64px.
- `illustrations/alignment/`: syllabus and curriculum illustrations, used at 40px.

SVG colors are self-contained so assets also render outside the application,
as specified in DESIGN.md. Update this family alongside the shared palette when
the brand changes. Within the interface, labels convey meaning; artwork is
decorative and has empty alternative text.

## Exploration archive

`explorations/faculty-dashboard/` preserves the earlier AI-generated PNGs and their prompts as
design references. They are not imported by the dashboard. The icon sheet has
unwanted shading/background pixels, and the raster texture has unverified repeat
seams. The finished SVGs replace those concepts wherever the dashboard uses artwork;
unselected character and object compositions remain archived rather than being
presented as production assets.

`explorations/faculty-dashboard/characters/` contains the transparent SME character
study and its built-in image-generation prompt. This direction was not selected;
the dashboard retains the specialist icon illustrations. The temporary character
placement prototype has been removed, and this study remains unimported.
