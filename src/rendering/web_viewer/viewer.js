/*
 * Interactive build-document viewer — consumes the vendored three.js r147 UMD
 * (window.THREE + THREE.GLTFLoader + THREE.OrbitControls, all loaded ahead of
 * this file in the same inline <script>).
 *
 * Per panel the generator emits a `.viewer-slot[data-detail=<slug>]` wrapping
 * the hero PNG plus an "Explore in 3D" button, and two sibling <script> tags:
 *   - <script type="application/json" id="detail-data-<slug>">  the payload
 *     (build_viewer_payload: parts keyed by GLB node name, dimensions)
 *   - <script type="text/plain"       id="detail-glb-<slug>">   base64 of the
 *     gzipped coarse web GLB (kept out of JSON so MBs never hit JSON.parse)
 *
 * On first button click a slot lazily builds a transparent-canvas renderer
 * over the PNG (max four WebGL contexts, zero cost until asked), decodes the
 * GLB in-browser via DecompressionStream, stamps each mesh with its part name,
 * and drives hover tooltips / pin / dimension callouts / explode. If WebGL or
 * DecompressionStream is unavailable the buttons are removed and the PNGs
 * stand alone (print / no-JS path).
 *
 * fillTooltip(el, payload, partName) is deliberately standalone and keyed only
 * by (payload, partName): it is the reuse surface a future 2D-sheet package
 * shares verbatim (same payload contract, same `.v-tip*` markup/CSS).
 */
(function () {
  "use strict";

  var THREE = window.THREE;
  var HL_COLOR = 0x000000; // resolved from --acc at activate time

  function hasWebGL() {
    try {
      var c = document.createElement("canvas");
      return !!(
        window.WebGLRenderingContext &&
        (c.getContext("webgl") || c.getContext("experimental-webgl"))
      );
    } catch (e) {
      return false;
    }
  }

  var CAPABLE =
    !!THREE &&
    typeof THREE.GLTFLoader === "function" &&
    hasWebGL() &&
    typeof DecompressionStream !== "undefined" &&
    typeof Response !== "undefined";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var slots = Array.prototype.slice.call(
      document.querySelectorAll(".viewer-slot")
    );
    if (!CAPABLE) {
      // No WebGL / no gzip decode: leave the PNGs, drop the dead affordance.
      slots.forEach(function (s) {
        var b = s.querySelector(".viewer-btn");
        if (b) b.remove();
      });
      return;
    }
    slots.forEach(setupSlot);
  });

  function setupSlot(slot) {
    var slug = slot.getAttribute("data-detail");
    var btn = slot.querySelector(".viewer-btn");
    if (!slug || !btn) return;
    btn.addEventListener(
      "click",
      function () {
        btn.disabled = true;
        btn.textContent = "Loading 3D…";
        activate(slot, slug, btn).catch(function (err) {
          console.error("[viewer] activation failed for " + slug, err);
          btn.disabled = false;
          btn.textContent = "Explore in 3D";
        });
      },
      { once: true }
    );
  }

  // --- HTML escaping (tooltip fill only touches server-provided strings) ----
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // --- CSS-var readout so highlight/line colors track the sheet's theme ----
  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    v = (v || "").trim();
    return v || fallback;
  }

  // --- gzip base64 -> ArrayBuffer (DecompressionStream, gated above) --------
  function decodeGlb(b64) {
    var bin = atob(b64.trim());
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var stream = new Blob([bytes])
      .stream()
      .pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).arrayBuffer();
  }

  // --- the reuse surface: fill a tooltip element from the payload row -------
  function fillTooltip(el, payload, partName) {
    var p = payload.parts[partName];
    if (!p) {
      el.style.display = "none";
      return false;
    }
    var stockLine = p.item;
    if (p.instance_count > 1) {
      stockLine = `${p.instance_index} of ${p.instance_count} · ${p.item}`;
    }
    var html = "";
    html += '<div class="v-tip-name">' + esc(p.reader_name || partName) + "</div>";
    html += '<div class="v-tip-stock">' + esc(stockLine) + "</div>";
    if (p.dims) html += '<div class="v-tip-dims">' + esc(p.dims) + "</div>";
    // The fabrication note rides WITH the overall dims: dims is the true finished
    // length ('48 in'), fab names the on-site cut that length alone would hide
    // (the trunk notch). Both are read from the same ProcessRecord the cut plan
    // reads, so the tooltip and the cut list never disagree.
    if (p.fab) html += '<div class="v-tip-fab">' + esc(p.fab) + "</div>";
    if (p.stub_of && p.stub_of.note) {
      html += '<div class="v-tip-stub">' + esc(p.stub_of.note) + "</div>";
    }
    var meta = [];
    if (p.material) meta.push(esc(p.material));
    meta.push("Qty " + esc(p.qty));
    html += '<div class="v-tip-meta">' + meta.join(" &middot; ") + "</div>";
    if (p.existing) {
      html += '<div class="v-tip-badge">EXISTING &mdash; NOT PURCHASED</div>';
    }
    if (p.specs && p.specs.length) {
      html += '<table class="v-tip-specs">';
      p.specs.forEach(function (s) {
        html +=
          "<tr><td>" + esc(s[0]) + "</td><td>" + esc(s[1]) + "</td></tr>";
      });
      html += "</table>";
    }
    if (p.assumptions) {
      html += '<div class="v-tip-assume">' + esc(p.assumptions) + "</div>";
    }
    el.innerHTML = html;
    el.style.display = "block";
    return true;
  }

  function positionTooltip(el, slot, x, y) {
    // x,y are slot-local px. Keep the tooltip inside the slot; flip sides near
    // the right/bottom edges so it never spills off the panel.
    var pad = 12;
    var w = el.offsetWidth || 200;
    var h = el.offsetHeight || 80;
    var sw = slot.clientWidth;
    var sh = slot.clientHeight;
    var left = x + 16;
    var top = y + 16;
    if (left + w + pad > sw) left = x - w - 16;
    if (left < pad) left = pad;
    if (top + h + pad > sh) top = y - h - 16;
    if (top < pad) top = pad;
    el.style.left = left + "px";
    el.style.top = top + "px";
  }

  function activate(slot, slug, btn) {
    var dataEl = document.getElementById("detail-data-" + slug);
    var glbEl = document.getElementById("detail-glb-" + slug);
    if (!dataEl || !glbEl) {
      return Promise.reject(new Error("missing payload/glb script for " + slug));
    }
    var payload = JSON.parse(dataEl.textContent);

    return decodeGlb(glbEl.textContent).then(function (buf) {
      return new Promise(function (resolve, reject) {
        new THREE.GLTFLoader().parse(
          buf,
          "",
          function (gltf) {
            try {
              build(slot, slug, btn, payload, gltf);
              resolve();
            } catch (e) {
              reject(e);
            }
          },
          reject
        );
      });
    });
  }

  function build(slot, slug, btn, payload, gltf) {
    HL_COLOR = new THREE.Color(cssVar("--acc", "#c85a24")).getHex();

    var img = slot.querySelector("img");
    var width = (img && img.clientWidth) || slot.clientWidth || 640;
    var height = (img && img.clientHeight) || slot.clientHeight || 480;

    var canvas = document.createElement("canvas");
    canvas.className = "v-canvas";
    slot.appendChild(canvas);

    var renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      alpha: true,
      antialias: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0); // transparent — paper shows through
    renderer.setSize(width, height, false);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100000);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x9099a5, 1.05));
    var key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(1, -1.4, 1.2);
    scene.add(key);
    var fill = new THREE.DirectionalLight(0xffffff, 0.35);
    fill.position.set(-1, 1, 0.4);
    scene.add(fill);

    var model = gltf.scene;
    scene.add(model);

    // The GLB ships glTF-default PBR materials (metalness 1.0) — a full metal
    // with no environment map renders BLACK in three.js (metals show only
    // reflections, and there are none here). Drop metalness to 0 so every part
    // reads as its matte base color under the lights, matching the flat,
    // diagram-legible look of the static PNG. Color and emissive are untouched.
    model.traverse(function (obj) {
      if (!obj.isMesh || !obj.material) return;
      var mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      mats.forEach(function (m) {
        if ("metalness" in m) m.metalness = 0.0;
        if ("roughness" in m) m.roughness = 0.75;
        m.needsUpdate = true;
      });
    });

    // Resolve a GLB node name back to a payload part key. three.js rewrites
    // node names on load: PropertyBinding.sanitizeNodeName turns "beam +Y" into
    // "beam_+Y", and a multi-primitive mesh becomes a group whose children get a
    // "_<n>" suffix ("beam_+Y_1"). The payload is keyed by the ORIGINAL
    // Placed.name ("beam +Y"), so match through the same sanitizer (and peel a
    // trailing primitive index) — otherwise every part whose name has a space
    // would be un-hoverable even though the GLB<->payload join test passes on
    // the raw (pre-sanitize) names.
    var sanitize =
      (THREE.PropertyBinding && THREE.PropertyBinding.sanitizeNodeName) ||
      function (n) { return n.replace(/\s/g, "_"); };
    var bySanitized = {};
    Object.keys(payload.parts).forEach(function (k) {
      bySanitized[sanitize(k)] = k;
    });
    function resolvePart(name) {
      if (!name) return null;
      if (payload.parts[name]) return name; // exact (single-word names)
      if (bySanitized[name]) return bySanitized[name]; // sanitized group node
      var m = name.match(/^(.*)_\d+$/); // primitive-suffixed child mesh
      if (m && bySanitized[m[1]]) return bySanitized[m[1]];
      return null;
    }

    // Stamp userData.partName onto each resolved node + its descendants; warn
    // for any mesh-owning node that resolves to nothing (a real join miss —
    // surfaced, not silent).
    var missing = [];
    (function stamp(obj, inherited) {
      var pn = inherited || resolvePart(obj.name);
      if (obj.isMesh && !pn && obj.name) missing.push(obj.name);
      if (pn) obj.userData.partName = pn;
      for (var i = 0; i < obj.children.length; i++) stamp(obj.children[i], pn);
    })(model, null);
    if (missing.length) {
      console.warn(
        "[viewer] " + slug + ": GLB mesh nodes absent from payload (not hoverable): ",
        missing
      );
    }

    // Index part -> {tops, meshes}. ``tops`` are the shallowest nodes carrying
    // the part (parent doesn't) — the ones explode translates, so a part that
    // three split into sibling meshes moves as a whole and a part wrapped in a
    // group isn't double-moved. ``meshes`` (all of them) drive hover emissive.
    var partNodes = {};
    model.traverse(function (obj) {
      var pn = obj.userData.partName;
      if (!pn) return;
      var entry = partNodes[pn] || (partNodes[pn] = { tops: [], origPos: [], meshes: [] });
      if (!obj.parent || obj.parent.userData.partName !== pn) {
        entry.tops.push(obj);
        entry.origPos.push(obj.position.clone());
      }
      if (obj.isMesh) entry.meshes.push(obj);
    });

    // Frame the camera to the model's world bbox.
    var box = new THREE.Box3().setFromObject(model);
    var center = box.getCenter(new THREE.Vector3());
    var size = box.getSize(new THREE.Vector3());
    var maxDim = Math.max(size.x, size.y, size.z) || 1;
    var dist = (maxDim / (2 * Math.tan((camera.fov * Math.PI) / 360))) * 1.5;
    var dir = new THREE.Vector3(1, -1, 0.65).normalize();
    camera.position.copy(center.clone().add(dir.multiplyScalar(dist)));
    camera.near = dist / 100;
    camera.far = dist * 100;
    camera.updateProjectionMatrix();

    var controls = new THREE.OrbitControls(camera, canvas);
    controls.target.copy(center);
    controls.enableDamping = true;
    controls.dampingFactor = 0.09;
    controls.update();

    // Dimension callouts live UNDER the model so any GLB up-axis transform
    // applies to them exactly as it does to the meshes (endpoints share the
    // model's mm frame). Hidden until toggled.
    var dimGroup = new THREE.Group();
    dimGroup.visible = false;
    model.add(dimGroup);
    var dimLabels = [];
    var dimColor = new THREE.Color(cssVar("--acc", "#c85a24"));
    (payload.dimensions || []).forEach(function (dim) {
      var p0 = new THREE.Vector3().fromArray(dim.p0);
      var p1 = new THREE.Vector3().fromArray(dim.p1);
      var geo = new THREE.BufferGeometry().setFromPoints([p0, p1]);
      var line = new THREE.Line(
        geo,
        new THREE.LineBasicMaterial({ color: dimColor.clone() })
      );
      dimGroup.add(line);
      var label = document.createElement("div");
      label.className = "v-dim-label";
      label.textContent = dim.label;
      label.style.display = "none";
      slot.appendChild(label);
      dimLabels.push({ el: label, mid: p0.clone().add(p1).multiplyScalar(0.5) });
    });

    // --- tooltip + hover/pin state ------------------------------------------
    var tip = document.createElement("div");
    tip.className = "v-tip";
    slot.appendChild(tip);

    var raycaster = new THREE.Raycaster();
    var pointer = new THREE.Vector2();
    var pendingPointer = null; // {x,y} slot-local, consumed on next frame
    var hovered = null; // partName currently emissive-lit
    var pinned = null; // partName pinned open

    function setEmissive(partName, hex) {
      var entry = partNodes[partName];
      if (!entry) return;
      entry.meshes.forEach(function (m) {
        if (!m.userData._matCloned) {
          m.material = m.material.clone();
          m.userData._matCloned = true;
        }
        if (m.material.emissive) m.material.emissive.setHex(hex);
      });
    }

    function highlight(partName) {
      if (hovered === partName) return;
      if (hovered && hovered !== pinned) setEmissive(hovered, 0x000000);
      hovered = partName;
      if (partName) setEmissive(partName, HL_COLOR);
    }

    function showTooltipFor(partName, sx, sy) {
      if (fillTooltip(tip, payload, partName)) {
        positionTooltip(tip, slot, sx, sy);
      }
    }

    function pin(partName, sx, sy) {
      pinned = partName;
      setEmissive(partName, HL_COLOR);
      tip.classList.add("pinned");
      fillTooltip(tip, payload, partName);
      tip.innerHTML += '<div class="v-tip-pinhint">Pinned — Esc or click empty space to clear</div>';
      positionTooltip(tip, slot, sx, sy);
    }

    function unpin() {
      if (!pinned) return;
      if (pinned !== hovered) setEmissive(pinned, 0x000000);
      pinned = null;
      tip.classList.remove("pinned");
      tip.style.display = "none";
    }

    function pickAt(sx, sy) {
      pointer.x = (sx / slot.clientWidth) * 2 - 1;
      pointer.y = -(sy / slot.clientHeight) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      var hits = raycaster.intersectObject(model, true);
      for (var i = 0; i < hits.length; i++) {
        var o = hits[i].object;
        while (o) {
          if (o.userData && o.userData.partName) return o.userData.partName;
          o = o.parent;
        }
      }
      return null;
    }

    canvas.addEventListener("pointermove", function (e) {
      var r = canvas.getBoundingClientRect();
      pendingPointer = { x: e.clientX - r.left, y: e.clientY - r.top };
    });
    canvas.addEventListener("pointerleave", function () {
      pendingPointer = null;
      if (!pinned) {
        highlight(null);
        tip.style.display = "none";
      }
    });
    canvas.addEventListener("pointerdown", function (e) {
      var r = canvas.getBoundingClientRect();
      var sx = e.clientX - r.left;
      var sy = e.clientY - r.top;
      var part = pickAt(sx, sy);
      if (part) {
        highlight(part);
        pin(part, sx, sy);
      } else {
        unpin();
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") unpin();
    });

    // --- controls toolbar ----------------------------------------------------
    var controlsEl = document.createElement("div");
    controlsEl.className = "v-controls";
    var dimBtn = document.createElement("button");
    dimBtn.type = "button";
    dimBtn.textContent = "Dimensions";
    dimBtn.setAttribute("aria-pressed", "false");
    dimBtn.addEventListener("click", function () {
      var on = dimGroup.visible;
      dimGroup.visible = !on;
      dimBtn.setAttribute("aria-pressed", String(!on));
      dimLabels.forEach(function (d) {
        d.el.style.display = on ? "none" : "block";
      });
    });
    controlsEl.appendChild(dimBtn);

    var explodeWrap = document.createElement("label");
    explodeWrap.appendChild(document.createTextNode("Explode"));
    var explode = document.createElement("input");
    explode.type = "range";
    explode.min = "0";
    explode.max = "1";
    explode.step = "0.01";
    explode.value = "0";
    explodeWrap.appendChild(explode);
    controlsEl.appendChild(explodeWrap);

    var hint = document.createElement("span");
    hint.className = "v-hint";
    hint.textContent = "Drag to orbit · scroll to zoom · hover a part";
    controlsEl.appendChild(hint);

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "v-close";
    closeBtn.textContent = "Close";
    controlsEl.appendChild(closeBtn);
    slot.appendChild(controlsEl);

    // explode: node.pos = orig + explodeVec·t, applied in each node's parent
    // frame (rotation-safe) so it holds under any GLB up-axis transform.
    var tmp = new THREE.Vector3();
    var q = new THREE.Quaternion();
    explode.addEventListener("input", function () {
      var t = parseFloat(explode.value);
      Object.keys(partNodes).forEach(function (name) {
        var entry = partNodes[name];
        var v = payload.parts[name] && payload.parts[name].explode;
        for (var i = 0; i < entry.tops.length; i++) {
          var node = entry.tops[i];
          var orig = entry.origPos[i];
          if (!v) {
            node.position.copy(orig);
            continue;
          }
          tmp.set(v[0], v[1], v[2]).multiplyScalar(t);
          if (node.parent) {
            node.parent.getWorldQuaternion(q).invert();
            tmp.applyQuaternion(q);
          }
          node.position.copy(orig).add(tmp);
        }
      });
    });

    // --- theme sync (highlight + dim line colors follow the sheet) ----------
    function refreshThemeColors() {
      HL_COLOR = new THREE.Color(cssVar("--acc", "#c85a24")).getHex();
      var c = new THREE.Color(cssVar("--acc", "#c85a24"));
      dimGroup.children.forEach(function (line) {
        if (line.material && line.material.color) line.material.color.copy(c);
      });
      if (hovered) setEmissive(hovered, HL_COLOR);
      if (pinned) setEmissive(pinned, HL_COLOR);
    }
    var mql = window.matchMedia("(prefers-color-scheme: dark)");
    if (mql.addEventListener) mql.addEventListener("change", refreshThemeColors);
    var themeObserver = new MutationObserver(refreshThemeColors);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    // --- teardown ------------------------------------------------------------
    var running = true;
    function teardown() {
      running = false;
      if (mql.removeEventListener) mql.removeEventListener("change", refreshThemeColors);
      themeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      canvas.remove();
      controlsEl.remove();
      tip.remove();
      dimLabels.forEach(function (d) { d.el.remove(); });
      window.removeEventListener("resize", resize);
      // bring the static PNG back and restore the launch affordance
      if (img) img.style.visibility = "";
      btn.hidden = false;
      btn.disabled = false;
      btn.textContent = "Explore in 3D";
      // re-arm the (once) button
      setupSlot(slot);
    }
    closeBtn.addEventListener("click", teardown);

    // --- resize --------------------------------------------------------------
    function resize() {
      var w = (img && img.clientWidth) || slot.clientWidth;
      var h = (img && img.clientHeight) || slot.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize);

    // --- render loop ---------------------------------------------------------
    var projected = new THREE.Vector3();
    function frame() {
      if (!running) return;
      requestAnimationFrame(frame);

      if (pendingPointer) {
        var pp = pendingPointer;
        pendingPointer = null;
        var part = pickAt(pp.x, pp.y);
        if (!pinned) {
          highlight(part);
          if (part) showTooltipFor(part, pp.x, pp.y);
          else tip.style.display = "none";
        }
        canvas.style.cursor = part ? "pointer" : "grab";
      }

      controls.update();
      renderer.render(scene, camera);

      if (dimGroup.visible) {
        for (var i = 0; i < dimLabels.length; i++) {
          var d = dimLabels[i];
          projected.copy(d.mid);
          model.localToWorld(projected);
          projected.project(camera);
          var vis = projected.z < 1;
          d.el.style.display = vis ? "block" : "none";
          if (vis) {
            d.el.style.left = ((projected.x + 1) / 2) * slot.clientWidth + "px";
            d.el.style.top = ((-projected.y + 1) / 2) * slot.clientHeight + "px";
          }
        }
      }
    }
    frame();

    // Canvas is live: hide the launch button (teardown restores it) and hide
    // the static PNG so it doesn't show through the transparent canvas.
    // visibility (not display) keeps the img's layout box, which sizes the
    // slot and the resize() math.
    btn.hidden = true;
    if (img) img.style.visibility = "hidden";
  }
})();
