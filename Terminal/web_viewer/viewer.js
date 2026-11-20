/* YAADO vehicle viewer: draws a vehicle config (JSON) in 3D with Three.js.
 *
 * Input: the output of BaseVehicleConfig.from_toml(path).model_dump_json(indent=2).
 * All lengths are meters. s is the axial distance from the nose tip, r the radial distance.
 * In the scene the nose points to +X and a point at axial position s sits at x = -s.
 * The schemas have no component positions yet (issue #43), so positions are assumptions
 * that are listed on the page.
 */
"use strict";

const DEG = Math.PI / 180;

/** Nose profile as [r, distanceFromTip] pairs. */
function nosePoints(type, radius, length, n = 40) {
  const pts = [];
  const rho = (radius * radius + length * length) / (2 * radius);
  for (let i = 0; i <= n; i++) {
    const x = (length * i) / n;
    let r;
    if (type === "conical") {
      r = (radius * x) / length;
    } else if (type === "hemispherical") {
      r = radius * Math.sqrt(Math.max(0, 1 - (1 - x / length) ** 2));
    } else {
      r = Math.max(0, Math.sqrt(Math.max(0, rho * rho - (length - x) ** 2)) + radius - rho);
    }
    pts.push([r, x]);
  }
  return pts;
}

/** Default nose length when the config has none: 3 diameters (0.5 for a hemisphere). */
function defaultNoseLength(type, diameter) {
  return type === "hemispherical" ? 0.5 * diameter : 3 * diameter;
}

/** Trapezoidal fin outline as [s, r] corners (LE root, TE root, TE tip, LE tip). */
function finOutline(fin, bodyLength, bodyRadius) {
  const notes = [];
  const cr = fin.chord_root ?? fin.span;
  if (fin.chord_root == null) notes.push("fin chord_root missing: set equal to span");
  const ct = fin.chord_tip ?? 0.4 * cr;
  if (fin.chord_tip == null) notes.push("fin chord_tip missing: set to 0.4 x root chord");
  let s0;
  if (fin.root_le_from_nose == null) {
    s0 = Math.max(0, bodyLength - cr);
    notes.push("fins flush with the aft end of the body");
  } else {
    s0 = fin.root_le_from_nose;
  }
  const off = fin.span * Math.tan(fin.sweep * DEG);
  const R = bodyRadius;
  return {
    corners: [[s0, R], [s0 + cr, R], [s0 + off + ct, R + fin.span], [s0 + off, R + fin.span]],
    notes,
  };
}

/** Planform of one half-wing as [s, y] corners; y is the distance from the centerline. */
function wingHalfOutline(wing, anchorS) {
  const b = wing.span;
  const area = (b * b) / wing.aspect_ratio;
  const cr = (2 * area) / (b * (1 + wing.taper_ratio));
  const ct = wing.taper_ratio * cr;
  const half = b / 2;
  const leRoot = anchorS - 0.25 * cr; // root quarter chord sits at the anchor
  const leTip = leRoot + half * Math.tan(wing.sweep * DEG) + 0.25 * cr - 0.25 * ct;
  return {
    corners: [[leRoot, 0], [leRoot + cr, 0], [leTip + ct, half], [leTip, half]],
    rootChord: cr,
    tipChord: ct,
    area,
  };
}

/** Pick the wing anchor: vehicle CG, then the wing's own CG, then mid-body. */
function wingAnchor(vehicle, wing, bodyLength) {
  const cg = vehicle.mass_properties?.cg_from_nose;
  if (cg != null) return { s: cg, note: "wings placed with the root quarter chord at the vehicle CG" };
  const own = wing.mass?.cg_from_nose;
  if (own != null) return { s: own, note: "wings placed with the root quarter chord at the wing's own CG" };
  return { s: bodyLength / 2, note: "wings placed with the root quarter chord at mid-body" };
}

/** Collect what to draw as plain data, so it can be checked without a renderer. */
function planVehicle(vehicle) {
  const assumptions = [];
  const bodies = Object.entries(vehicle.bodies ?? {});
  if (bodies.length === 0) throw new Error("The vehicle has no body, nothing to draw around.");
  const [bodyName, body] = bodies.reduce((a, b) => (b[1].length > a[1].length ? b : a));
  const length = body.length;
  const radius = body.diameter / 2;
  const noseType = body.nose_type ?? "ogive";
  let noseLength = body.nose_length;
  if (noseLength == null) {
    noseLength = defaultNoseLength(noseType, body.diameter);
    assumptions.push(`nose_length missing: set to ${noseLength.toFixed(3)} m`);
  }
  noseLength = Math.min(noseLength, length);
  const items = [];
  items.push({ name: bodyName, kind: "body", drawn: true,
    nose: nosePoints(noseType, radius, noseLength), length, radius, noseLength });
  for (const [name, f] of Object.entries(vehicle.aero_surfaces ?? {})) {
    if (f.type === "fins") {
      const o = finOutline(f, length, radius);
      assumptions.push(...o.notes.map((t) => `${name}: ${t}`));
      items.push({ name, kind: "fins", drawn: true, count: f.count, corners: o.corners });
    } else if (f.type === "wing") {
      const a = wingAnchor(vehicle, f, length);
      assumptions.push(`${name}: ${a.note}`);
      const o = wingHalfOutline(f, a.s);
      items.push({ name, kind: "wing", drawn: true, dihedral: f.dihedral ?? 0, corners: o.corners });
    } else {
      items.push({ name, kind: f.type, drawn: false });
    }
  }
  for (const [name, p] of Object.entries(vehicle.propulsion ?? {})) {
    if (p.type === "solid_motor" && p.casing_length != null && p.casing_diameter != null) {
      assumptions.push(`${name}: motor casing drawn flush with the aft end of the body`);
      items.push({ name, kind: "solid motor", drawn: true,
        s0: Math.max(0, length - p.casing_length), s1: length, radius: p.casing_diameter / 2 });
    } else {
      items.push({ name, kind: (p.type ?? "propulsion").replace("_", " "), drawn: false });
    }
  }
  const cg = vehicle.mass_properties?.cg_from_nose ?? null;
  return { items, assumptions, length, radius, cg };
}

if (typeof module !== "undefined") {
  module.exports = { nosePoints, defaultNoseLength, finOutline, wingHalfOutline, wingAnchor, planVehicle };
}

/* ---------------------------- browser part ---------------------------- */
if (typeof window !== "undefined" && typeof document !== "undefined") {
  const $ = (id) => document.getElementById(id);
  let THREE = null;
  let scene, camera, renderer, controls;
  let groups = new Map();

  async function init() {
    try {
      const [three, addons] = await Promise.all([
        import("three"),
        import("three/addons/controls/OrbitControls.js"),
      ]);
      THREE = three;
      const canvas = $("view");
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1000);
      controls = new addons.OrbitControls(camera, canvas);
      scene.add(new THREE.AmbientLight(0xffffff, 0.7));
      const sun = new THREE.DirectionalLight(0xffffff, 1.4);
      sun.position.set(2, 4, 3);
      scene.add(sun);
      resize();
      window.addEventListener("resize", resize);
      renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
    } catch (e) {
      $("error").textContent = "Could not load Three.js from the CDN (offline?): " + e.message;
    }
  }

  function resize() {
    const main = document.querySelector("main");
    const w = main.clientWidth, h = main.clientHeight || 400;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  const COLORS = { body: 0x8fa3bf, fins: 0xd98c3a, wing: 0x4aa37a, "solid motor": 0x9b6bd1 };

  function plate(corners, thickness, toXY) {
    const shape = new THREE.Shape();
    corners.forEach((c, i) => { const [x, y] = toXY(c); i ? shape.lineTo(x, y) : shape.moveTo(x, y); });
    shape.closePath();
    const g = new THREE.ExtrudeGeometry(shape, { depth: thickness, bevelEnabled: false });
    g.translate(0, 0, -thickness / 2);
    return g;
  }

  function mat(kind) {
    return new THREE.MeshStandardMaterial({ color: COLORS[kind] ?? 0xaaaaaa, side: THREE.DoubleSide,
      roughness: 0.55, metalness: 0.2 });
  }

  function build(plan) {
    for (const g of groups.values()) scene.remove(g);
    groups = new Map();
    for (const it of plan.items) {
      if (!it.drawn) continue;
      const group = new THREE.Group();
      if (it.kind === "body") {
        const pts = it.nose.map(([r, d]) => new THREE.Vector2(r, -d));
        pts.push(new THREE.Vector2(it.radius, -it.length), new THREE.Vector2(0, -it.length));
        const mesh = new THREE.Mesh(new THREE.LatheGeometry(pts, 64), mat("body"));
        mesh.rotation.z = -Math.PI / 2; // lathe axis +Y -> scene +X (nose forward)
        group.add(mesh);
      } else if (it.kind === "fins") {
        const cr = it.corners[1][0] - it.corners[0][0];
        const t = Math.max(0.002, 0.03 * cr);
        for (let k = 0; k < it.count; k++) {
          const m = new THREE.Mesh(plate(it.corners, t, ([s, r]) => [-s, r]), mat("fins"));
          m.rotation.x = (2 * Math.PI * k) / it.count;
          group.add(m);
        }
      } else if (it.kind === "wing") {
        const cr = it.corners[1][0] - it.corners[0][0];
        const t = Math.max(0.002, 0.03 * cr);
        for (const sign of [1, -1]) {
          const m = new THREE.Mesh(plate(it.corners, t, ([s, y]) => [-s, y]), mat("wing"));
          m.rotation.x = sign * (Math.PI / 2 - it.dihedral * DEG);
          group.add(m);
        }
      } else if (it.kind === "solid motor") {
        const len = it.s1 - it.s0;
        const geo = new THREE.CylinderGeometry(it.radius, it.radius, len, 48);
        const m = new THREE.Mesh(geo, mat("solid motor"));
        m.material.transparent = true;
        m.material.opacity = 0.55;
        m.rotation.z = -Math.PI / 2;
        m.position.x = -(it.s0 + it.s1) / 2;
        group.add(m);
      }
      groups.set(it.name, group);
      scene.add(group);
    }
    if (plan.cg != null) {
      const cg = new THREE.Mesh(new THREE.SphereGeometry(plan.radius * 0.18, 16, 12),
        new THREE.MeshBasicMaterial({ color: 0xe03a3a }));
      cg.position.x = -plan.cg;
      const group = new THREE.Group();
      group.add(cg);
      groups.set("center of gravity", group);
      scene.add(group);
      plan.items.push({ name: "center of gravity", kind: "marker", drawn: true });
    }
    const L = plan.length;
    controls.target.set(-L / 2, 0, 0);
    camera.position.set(-L / 2 + 0.4 * L, 0.5 * L, 1.3 * L);
    camera.near = L / 200;
    camera.far = L * 50;
    camera.updateProjectionMatrix();
  }

  function show(vehicle) {
    $("error").textContent = "";
    const plan = planVehicle(vehicle);
    $("name").textContent = vehicle.name ?? "(unnamed vehicle)";
    $("desc").textContent = vehicle.description ?? "";
    build(plan);
    const ul = $("components");
    ul.replaceChildren();
    for (const it of plan.items) {
      const li = document.createElement("li");
      const label = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = it.drawn;
      box.disabled = !it.drawn;
      box.addEventListener("change", () => { groups.get(it.name).visible = box.checked; });
      const kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = it.drawn ? it.kind : it.kind + " (not drawn)";
      label.append(box, document.createTextNode(it.name + " "), kind);
      li.append(label);
      ul.append(li);
    }
    const al = $("assumptions");
    al.replaceChildren();
    const lines = [
      "The schemas have no component positions yet (issue #43); positions below are assumptions.",
      ...plan.assumptions,
    ];
    for (const t of lines) { const li = document.createElement("li"); li.textContent = t; al.append(li); }
  }

  async function loadFile(file) {
    try {
      if (!THREE) throw new Error("Three.js is not loaded.");
      show(JSON.parse(await file.text()));
    } catch (e) {
      $("error").textContent = "Cannot show this file: " + e.message;
    }
  }

  $("file").addEventListener("change", (e) => { if (e.target.files[0]) loadFile(e.target.files[0]); });
  window.addEventListener("dragover", (e) => { e.preventDefault(); $("drop").classList.add("over"); });
  window.addEventListener("dragleave", () => $("drop").classList.remove("over"));
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    $("drop").classList.remove("over");
    if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
  });
  init();
}
