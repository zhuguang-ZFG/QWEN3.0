// Generate AVIF/WebP variants for raster images in public/assets.
// SVGs are skipped (vector is already optimal).
import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const ASSETS_DIR = new URL("../public/assets/", import.meta.url);
const SKIP = new Set([".gitkeep"]);

async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

async function needsRebuild(srcPath, outPath) {
  if (!(await exists(outPath))) return true;
  const src = await stat(srcPath);
  const out = await stat(outPath);
  return src.mtimeMs > out.mtimeMs;
}

async function processFile(name) {
  const ext = path.extname(name).toLowerCase();
  if (![".png", ".jpg", ".jpeg", ".webp"].includes(ext)) return;
  if (SKIP.has(name)) return;

  const srcPath = fileURLToPath(new URL(name, ASSETS_DIR));
  const base = path.basename(name, ext);
  const webpName = `${base}.webp`;
  const avifName = `${base}.avif`;
  const webpPath = fileURLToPath(new URL(webpName, ASSETS_DIR));
  const avifPath = fileURLToPath(new URL(avifName, ASSETS_DIR));

  // Generate WebP if source is not already WebP or if outdated.
  if (ext !== ".webp" && (await needsRebuild(srcPath, webpPath))) {
    await sharp(srcPath).webp({ quality: 85 }).toFile(webpPath);
    console.log(`Generated ${webpName}`);
  }

  // Generate AVIF if outdated.
  if (await needsRebuild(srcPath, avifPath)) {
    await sharp(srcPath)
      .avif({ quality: 75, effort: 4 })
      .toFile(avifPath);
    console.log(`Generated ${avifName}`);
  }
}

async function main() {
  const entries = await readdir(ASSETS_DIR, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) continue;
    await processFile(entry.name);
  }
  console.log("Image optimization complete");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
