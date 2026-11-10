import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const source = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(source);
const run = (args, options = {}) =>
  execFileSync("git", ["-c", "core.fsmonitor=false", ...args], {
    cwd: root,
    encoding: "utf8",
    ...options,
  }).trim();
const origin = run(["remote", "get-url", "origin"]);
if (
  !/^(https:\/\/github\.com\/|git@github\.com:)LSPU-EquipED\/EquipED(?:\.git)?$/.test(
    origin,
  )
) {
  throw new Error(
    "Confirm the deployment destination before publishing from a fork.",
  );
}
execFileSync(process.execPath, [path.join(source, "build.mjs")], {
  stdio: "inherit",
});
let parent;
try {
  const remote = run([
    "ls-remote",
    "--exit-code",
    "--heads",
    "origin",
    "gh-pages",
  ]);
  parent = remote.split(/\s+/)[0];
  run(["fetch", "origin", "refs/heads/gh-pages"]);
} catch (error) {
  if (error.status !== 2) throw error;
}
const temporary = await mkdtemp(path.join(tmpdir(), "equiped-pages-index-"));
try {
  const gitDirectory = run(["rev-parse", "--absolute-git-dir"]);
  const env = { ...process.env, GIT_INDEX_FILE: path.join(temporary, "index") };
  const stage = (args) =>
    run(
      [
        `--git-dir=${gitDirectory}`,
        `--work-tree=${path.join(source, "dist")}`,
        ...args,
      ],
      { cwd: path.join(source, "dist"), env },
    );
  stage(["read-tree", "--empty"]);
  stage(["add", "--all", "--", "."]);
  const tree = stage(["write-tree"]);
  const args = ["commit-tree", tree, "-m", "Publish EquipED research site"];
  if (parent) args.push("-p", parent);
  const commit = run(args);
  run(["push", "origin", `${commit}:refs/heads/gh-pages`], {
    stdio: ["ignore", "pipe", "inherit"],
  });
  console.log(
    "Published the static build to gh-pages. Check the GitHub Pages build before sharing its URL.",
  );
} finally {
  await rm(temporary, { recursive: true, force: true });
}
