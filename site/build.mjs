import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const source = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(source);
const output = path.join(source, "dist");
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
for (const name of ["index.html", "styles.css", "main.js"]) {
  await cp(path.join(source, name), path.join(output, name), {
    recursive: true,
  });
}
const copies = [
  // Public-site assets are explicit: never copy an entire screenshot directory.
  ["site/assets/screenshots/sign-in.jpg", "assets/screenshots/sign-in.jpg"],
  ["libs/ui/src/theme/tokens.css", "assets/theme/tokens.css"],
  ...[
    "PublicSans-Regular.woff2",
    "PublicSans-SemiBold.woff2",
    "PublicSans-Bold.woff2",
    "PublicSans-OFL.txt",
  ].map((name) => [`libs/ui/src/assets/fonts/${name}`, `assets/fonts/${name}`]),
  [
    "libs/ui/src/assets/brand/equiped-symbol.svg",
    "assets/brand/equiped-symbol.svg",
  ],
  ...[
    "content-inspection",
    "curriculum-planning",
    "inclusive-discussion",
    "innovation-workbench",
  ].map((name) => [
    `apps/faculty/src/features/evaluation/assets/workspace/illustrations/${name}.svg`,
    `assets/illustrations/${name}.svg`,
  ]),
];
for (const [from, to] of copies) {
  await mkdir(path.dirname(path.join(output, to)), { recursive: true });
  await cp(path.join(root, from), path.join(output, to));
}
// Reuse the small, already embedded seal from the README lockup unchanged.
const lockup = await readFile(
  path.join(root, "assets/branding/equiped-lspu.svg"),
  "utf8",
);
const seal = lockup.match(/href="data:image\/png;base64,([^"]+)"/);
if (!seal)
  throw new Error("The institutional lockup is missing its embedded seal.");
await writeFile(
  path.join(output, "assets/brand/lspu-logo.png"),
  Buffer.from(seal[1], "base64"),
);
await writeFile(path.join(output, ".nojekyll"), "");
console.log(`Built EquipED research site: ${output}`);
