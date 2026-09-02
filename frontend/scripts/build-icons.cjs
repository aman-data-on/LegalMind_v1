#!/usr/bin/env node
/**
 * Build the app icons from the owner-supplied artwork.
 *
 *   node scripts/build-icons.cjs [path/to/source.png]
 *
 * Source default: ../assets/app-icon-source.png (owner-supplied 2026-09-01).
 * It lives under frontend/assets/ rather than the repo root or public/: it is
 * tracked, because that is what makes these icons reproducible, but assets/ is
 * not served by Next — only public/ is — so the 1.3 MB master never reaches a
 * browser. Only the three generated files below do.
 * Outputs, per Next 16's file conventions (verified against
 * node_modules/next/dist/docs/.../app-icons.md — this repo's AGENTS.md warns not
 * to assume them):
 *
 *   src/app/favicon.ico     16 + 32 + 48, the tab/bookmark icon
 *   src/app/icon.png        512, modern browsers and Android
 *   src/app/apple-icon.png  180, iOS home screen
 *
 * Next emits the <link> tags itself and derives `sizes` from each file, so
 * layout.tsx needs no `metadata.icons` entry.
 *
 * ── Why the source is cropped and squared ────────────────────────────────────
 * The supplied art is 1536×1024 with the icon tile floating inside it on a
 * transparent ground. Measured opaque bounds (alpha >= 250): x 266..1269,
 * y 16..972 — a 1004×957 tile, i.e. 4.8% wider than tall.
 *
 * A favicon frame is square. Handing a browser a non-square PNG means it
 * letterboxes or stretches on its own terms, so squaring is not optional; the
 * only question is how. Two options were real:
 *
 *   contain — keep the 1.048 ratio, pad transparent bars top and bottom. Costs
 *             ~2.4% of height each side, so the icon renders visibly smaller
 *             than its neighbours in a tab strip. "Fits" less well, not more.
 *   square  — scale to an exact square, a 4.8% vertical stretch.
 *
 * `square` is used. This is an app-icon TILE — square by definition — and its
 * non-squareness is an artifact of the 3:2 canvas it was rendered on, not
 * intent: at every alpha threshold the ratio is the same 1.047–1.049, and the
 * rounded corners are correspondingly asymmetric. Squaring restores the tile and
 * fills the frame edge to edge. 4.8% on a monogram is below the perceptual
 * threshold at 16–512px.
 *
 * To choose `contain` instead, set FIT=contain in the environment. Nothing else
 * changes.
 */
const fs = require("node:fs");
const path = require("node:path");
const sharp = require("sharp");

const SRC = process.argv[2]
  ?? path.join(__dirname, "..", "assets", "app-icon-source.png");
const OUT = path.join(__dirname, "..", "src", "app");
const FIT = process.env.FIT === "contain" ? "contain" : "square";

/** Encode settings, shared by every output.
 *
 *  A 256-colour palette rather than truecolour: it takes the 512px icon from
 *  394 KB to 84 KB — a 4.7× reduction — and the two are indistinguishable side
 *  by side at 160px and at 512px. An icon is fetched on page load; 394 KB of
 *  gradient for a tab mark is not a reasonable price.
 *
 *  128 colours was measured too (31 KB) and also looked clean at icon sizes, but
 *  128 levels across a full-tile gradient is where banding begins to show on a
 *  large Android launcher or an install prompt, so it is not taken. */
const PNG_OPTS = { palette: true, colours: 256, dither: 1.0, compressionLevel: 9 };

/** The tile's opaque bounding box — excludes the soft outer glow, which would
 *  otherwise add a transparent halo row and make the icon sit small. */
async function opaqueBounds(file) {
  const meta = await sharp(file).metadata();
  const raw = await sharp(file).ensureAlpha().raw().toBuffer();
  let x0 = meta.width, y0 = meta.height, x1 = -1, y1 = -1;
  for (let y = 0; y < meta.height; y++) {
    for (let x = 0; x < meta.width; x++) {
      if (raw[(y * meta.width + x) * 4 + 3] < 250) continue;
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  if (x1 < 0) throw new Error(`${file}: no opaque pixels found`);
  return { left: x0, top: y0, width: x1 - x0 + 1, height: y1 - y0 + 1 };
}

/** A minimal ICO container holding PNG frames.
 *
 *  sharp cannot write .ico, and the format needs no library: a 6-byte header, a
 *  16-byte directory entry per frame, then the frames themselves. PNG frames are
 *  read by every browser that matters (and IE11+). Width/height of 256 are
 *  encoded as 0 per the spec — not reachable here, but the guard is cheap. */
function buildIco(frames) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);            // reserved
  header.writeUInt16LE(1, 2);            // type: 1 = icon
  header.writeUInt16LE(frames.length, 4);

  const dir = Buffer.alloc(16 * frames.length);
  let offset = header.length + dir.length;
  frames.forEach((f, i) => {
    const at = i * 16;
    dir.writeUInt8(f.size >= 256 ? 0 : f.size, at);      // width
    dir.writeUInt8(f.size >= 256 ? 0 : f.size, at + 1);  // height
    dir.writeUInt8(0, at + 2);                           // palette count
    dir.writeUInt8(0, at + 3);                           // reserved
    dir.writeUInt16LE(1, at + 4);                        // colour planes
    dir.writeUInt16LE(32, at + 6);                       // bits per pixel
    dir.writeUInt32LE(f.data.length, at + 8);
    dir.writeUInt32LE(offset, at + 12);
    offset += f.data.length;
  });
  return Buffer.concat([header, dir, ...frames.map((f) => f.data)]);
}

(async () => {
  if (!fs.existsSync(SRC)) throw new Error(`source not found: ${SRC}`);
  const box = await opaqueBounds(SRC);
  const ratio = (box.width / box.height).toFixed(4);
  console.log(`  source ${SRC}`);
  console.log(`  tile   ${box.width}×${box.height} at (${box.left},${box.top})  ratio ${ratio}`);
  console.log(`  fit    ${FIT}`);

  const tile = await sharp(SRC).extract(box).png().toBuffer();

  /** One square PNG at `size`. `square` stretches to fill; `contain` pads.
   *
   *  A mild unsharp pass at 32px and below. Downscaling a 1004px tile to 16px
   *  softens the fine strokes — the scales glyph turns to a grey blob — and a
   *  sigma-0.6 sharpen recovers enough definition to read, verified by eye at
   *  10× magnification. Not applied above 32px: there the strokes survive on
   *  their own and sharpening only adds ringing on the monogram's edges. */
  const at = async (size) => {
    let img = sharp(tile).resize(size, size,
      FIT === "contain"
        ? { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } }
        : { fit: "fill" });
    if (size <= 32) img = img.sharpen({ sigma: 0.6, m1: 1, m2: 2 });
    return img.png(PNG_OPTS).toBuffer();
  };

  // favicon.ico — 16/32/48. 16 is what a tab actually shows; 48 covers Windows
  // taskbar and bookmark grids.
  const frames = [];
  for (const size of [16, 32, 48]) frames.push({ size, data: await at(size) });
  fs.writeFileSync(path.join(OUT, "favicon.ico"), buildIco(frames));
  console.log(`  wrote favicon.ico      ${frames.map((f) => f.size).join(" + ")}`);

  fs.writeFileSync(path.join(OUT, "icon.png"), await at(512));
  console.log("  wrote icon.png         512×512");

  // iOS: full-bleed, no transparency, and no rounded corners of its own.
  //
  // Two reasons this is not just `at(180)`. iOS ignores alpha and composites on
  // BLACK, so the tile's transparent rounded corners would become hard black
  // notches. And iOS applies its own squircle mask, so a tile that is already
  // rounded gets rounded twice — a visible double bevel.
  //
  // Both go away by cropping the tile's own corners off: take the centre 86% so
  // the rounding falls outside the frame, leaving an opaque square for iOS to
  // mask however it likes. The mark sits well inside that margin, so nothing of
  // it is lost. (A first attempt flattened onto a colour sampled 8% in from a
  // corner; it picked up the blue gradient rather than the dark edge, which is
  // the sort of thing sampling a single point does.)
  const keep = 0.86;
  const cw = Math.round(box.width * keep), chh = Math.round(box.height * keep);
  const appleSquare = await sharp(tile)
    .extract({
      left: Math.round((box.width - cw) / 2),
      top: Math.round((box.height - chh) / 2),
      width: cw, height: chh,
    })
    .resize(180, 180, { fit: "fill" })
    .flatten({ background: { r: 0, g: 0, b: 0, alpha: 1 } })  // nothing left to show
    .png(PNG_OPTS)
    .toBuffer();
  fs.writeFileSync(path.join(OUT, "apple-icon.png"), appleSquare);
  console.log(`  wrote apple-icon.png   180×180, full-bleed (centre ${Math.round(keep * 100)}%)`);
})();
