# EquipED research site

A static GitHub Pages showcase for the thesis. It uses Public Sans, shared EquipED
color tokens, and existing product illustrations. It is separate from the two
application portals and needs no API, database, account, or inference service.

## Build and preview

From the repository root:

```sh
pnpm site:check
python3 -m http.server 4173 --bind 127.0.0.1 --directory site/dist
```

Open `http://127.0.0.1:4173`. The build copies only explicitly selected public
assets into ignored `site/dist/`; shared fonts include their license. Relative
URLs support GitHub project-site paths such as `/EquipED/`.

## Publish

With repository push access, run `pnpm site:publish`. It rebuilds, creates a
static-only commit on `gh-pages`, and pushes without modifying the source branch
or its Git index. Configure GitHub Pages to publish the root of `gh-pages`.
Deployment conflicts fail rather than force-pushing. Confirm the Pages build
finishes before sharing the site. Publishing is manual; source changes are not
deployed merely by merging them.

## Content and privacy

The exact thesis title, team, and adviser are in `index.html`. Results report the
archived synthetic GAD comparison with its original limitations. The only
application capture is the empty public sign-in screen. Do not add authenticated
records, private module passages, account details, or credentials. Additional
images require explicit review and inclusion in the build asset list.
