/* labels3d.mjs
   NOTE (known-benign console warning): "Multiple instances of Three.js" appears
   because 3d-force-graph.min.js is a self-contained UMD bundle (own three copy)
   while this module imports the vendored ESM three via the import map. The two
   copies interoperate (labels attach as nodeThreeObject sprites; verified
   rendering correct across all views). Unifying would require vendoring the
   full ESM dependency tree (~15 packages) for zero functional gain. */
/* labels3d.mjs-orig — label sprite factory for the 3D concept atlas.
   Loads three (vendored, via import map) and exposes a minimal API:
   window.Atlas3D = { THREE, makeLabel(text, color, textHeight) -> THREE.Sprite } */
import * as THREE from "three";

/* `halo` is the colour painted behind the glyphs. It used to be hard-coded
   parchment, which in dark mode put a bright cream slab behind every label
   and turned a dense graph into an unreadable wall — the halo has to follow
   the theme, like everything else drawn to a canvas. */
function makeLabel(text, color, textHeight = 6, halo) {
  const font = "600 64px Inter, system-ui, sans-serif";
  const pad = 16;
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d");
  ctx.font = font;
  const m = ctx.measureText(text);
  c.width = Math.ceil(m.width + pad * 2);
  c.height = 96;
  const ctx2 = c.getContext("2d");
  ctx2.font = font;
  ctx2.textAlign = "center";
  ctx2.textBaseline = "middle";
  // parchment halo
  ctx2.lineWidth = 12;
  ctx2.strokeStyle = halo || "rgba(246,241,229,0.92)";
  ctx2.strokeText(text, c.width / 2, c.height / 2 + 2);
  ctx2.fillStyle = color;
  ctx2.fillText(text, c.width / 2, c.height / 2 + 2);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
  const spr = new THREE.Sprite(mat);
  spr.scale.set(textHeight * (c.width / c.height), textHeight, 1);
  return spr;
}

window.Atlas3D = { THREE, makeLabel };
console.info("Atlas3D labels module ready (three r" + THREE.REVISION + ")");
