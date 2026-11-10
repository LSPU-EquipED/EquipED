import { lstat, readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const output = path.join(path.dirname(fileURLToPath(import.meta.url)), "dist");
const html = await readFile(path.join(output, "index.html"), "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
if (new Set(ids).size !== ids.length) throw new Error("Duplicate page IDs.");
let references = 0;
const check = async (reference, from) => {
  if (/^(?:https?:|data:|mailto:)/.test(reference)) return;
  if (reference.startsWith("/"))
    throw new Error(`Project-site URL must be relative: ${reference}`);
  if (reference.startsWith("#")) {
    if (!ids.includes(reference.slice(1)))
      throw new Error(`Unknown anchor: ${reference}`);
    return;
  }
  const target = path.resolve(
    path.dirname(from),
    decodeURIComponent(reference.split(/[?#]/)[0]),
  );
  if (!target.startsWith(output + path.sep))
    throw new Error("Asset escapes the site output.");
  if (!(await stat(target)).isFile())
    throw new Error(`Missing asset: ${reference}`);
  references++;
};
for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g))
  await check(match[1], path.join(output, "index.html"));
for (const css of ["styles.css", "assets/theme/tokens.css"]) {
  const content = await readFile(path.join(output, css), "utf8");
  for (const match of content.matchAll(/url\(\s*['"]?([^'"\s)]+)['"]?\s*\)/g))
    await check(match[1], path.join(output, css));
}
let files = 0,
  bytes = 0;
const inspect = async (directory) => {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    const info = await lstat(file);
    if (info.isSymbolicLink())
      throw new Error("Deployment must not contain symlinks.");
    if (entry.isDirectory()) await inspect(file);
    else {
      const relative = path.relative(output, file);
      if (
        relative !== ".nojekyll" &&
        !/\.(?:html|css|js|svg|png|jpg|woff2|txt)$/.test(relative)
      )
        throw new Error(`Unexpected published file: ${relative}`);
      files++;
      bytes += info.size;
    }
  }
};
await inspect(output);
if (bytes > 1024 * 1024)
  throw new Error("The static site exceeds its 1 MiB asset budget.");
if (!html.includes("Dr. Mia V. Villarica") || !html.includes("Jose Aquino III"))
  throw new Error("Missing confirmed research attribution.");
console.log(
  `Site check passed: ${ids.length} unique IDs, ${references} asset references, ${files} public files, ${Math.ceil(bytes / 1024)} KiB.`,
);
