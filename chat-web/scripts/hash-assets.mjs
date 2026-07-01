// Build chat-web with hashed JS/CSS filenames for immutable caching.
// Copies everything to chat-web/dist/, renames js/*.js and styles.css with
// content hashes, and rewrites HTML references accordingly.
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const ROOT = new URL("../", import.meta.url);
const DIST = new URL("../dist/", import.meta.url);

const IGNORED_TOP_LEVEL = new Set(["dist", "scripts", "node_modules", ".git"]);

async function exists(url) {
  try {
    await stat(url);
    return true;
  } catch {
    return false;
  }
}

async function emptyDir(dir) {
  if (await exists(dir)) {
    await rm(dir, { recursive: true, force: true });
  }
  await mkdir(dir, { recursive: true });
}

async function copyRecursive(srcDir, destDir) {
  const entries = await readdir(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    const srcName = entry.name;
    if (srcDir.pathname === ROOT.pathname && IGNORED_TOP_LEVEL.has(srcName)) {
      continue;
    }
    if (entry.isDirectory()) {
      const srcUrl = new URL(srcName + "/", srcDir);
      const destUrl = new URL(srcName + "/", destDir);
      await mkdir(destUrl, { recursive: true });
      await copyRecursive(srcUrl, destUrl);
    } else {
      const srcUrl = new URL(srcName, srcDir);
      const destUrl = new URL(srcName, destDir);
      await copyFile(srcUrl, destUrl);
    }
  }
}

async function hashFile(url) {
  const content = await readFile(url);
  const hash = createHash("sha256").update(content).digest("hex").slice(0, 8);
  return { content, hash };
}

function hashedName(filePath, hash) {
  const ext = path.extname(filePath);
  const base = path.basename(filePath, ext);
  return `${base}.${hash}${ext}`;
}

async function main() {
  console.log("Cleaning dist...");
  await emptyDir(DIST);

  console.log("Copying source files...");
  await copyRecursive(ROOT, DIST);

  // Compute hashes for JS/CSS assets.
  // Hash js/*.js (subdirectory) AND root-level chat-*.js files.
  const jsMap = new Map();

  // 1) Hash js/ subdirectory files
  const jsDir = new URL("js/", DIST);
  const jsFiles = (await readdir(jsDir)).filter((n) => n.endsWith(".js"));
  for (const name of jsFiles) {
    const srcUrl = new URL(name, jsDir);
    const { hash } = await hashFile(srcUrl);
    const newName = hashedName(name, hash);
    const destUrl = new URL(newName, jsDir);
    await copyFile(srcUrl, destUrl);
    await rm(srcUrl);
    jsMap.set(`js/${name}`, `js/${newName}`);
    console.log(`Hashed js/${name} -> js/${newName}`);
  }

  // 2) Hash root-level chat-*.js files (previously missed — immutable cache without bust)
  const rootFiles = (await readdir(DIST)).filter(
    (n) => n.startsWith("chat-") && n.endsWith(".js"),
  );
  for (const name of rootFiles) {
    const srcUrl = new URL(name, DIST);
    const { hash } = await hashFile(srcUrl);
    const newName = hashedName(name, hash);
    const destUrl = new URL(newName, DIST);
    await copyFile(srcUrl, destUrl);
    await rm(srcUrl);
    jsMap.set(name, newName);
    console.log(`Hashed ${name} -> ${newName}`);
  }

  const stylesUrl = new URL("styles.css", DIST);
  let cssMap = new Map();
  if (await exists(stylesUrl)) {
    const { hash } = await hashFile(stylesUrl);
    const newName = hashedName("styles.css", hash);
    const newUrl = new URL(newName, DIST);
    await copyFile(stylesUrl, newUrl);
    await rm(stylesUrl);
    cssMap.set("styles.css", newName);
    console.log(`Hashed styles.css -> ${newName}`);
  }

  // Rewrite HTML references.
  const htmlFiles = [];
  async function collectHtml(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        await collectHtml(new URL(entry.name + "/", dir));
      } else if (entry.name.endsWith(".html")) {
        htmlFiles.push(new URL(entry.name, dir));
      }
    }
  }
  await collectHtml(DIST);

  for (const htmlUrl of htmlFiles) {
    let html = await readFile(htmlUrl, "utf8");
    for (const [oldPath, newPath] of jsMap) {
      html = html.replaceAll(oldPath, newPath);
    }
    for (const [oldPath, newPath] of cssMap) {
      html = html.replaceAll(oldPath, newPath);
    }
    await writeFile(htmlUrl, html);
  }
  console.log(`Rewrote ${htmlFiles.length} HTML files`);
  console.log("Build complete: chat-web/dist/");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
