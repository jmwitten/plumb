/*
 * Inspector Mode — the compiler-as-IDE front end (task INSPECTOR).
 *
 * A single self-contained page: a three.js model on the left, a four-question
 * inspector panel on the right. Click a component -> the panel answers, ENTIRELY
 * from the emitted payload:
 *   1. WHAT IS THIS        (descriptor)
 *   2. WHY IS IT HERE      (provenance: authored vs derived + chain)
 *   3. HOW DO WE KNOW      (verification: EXPLAINED findings + the honest
 *      IT'S CORRECT         seven-family coverage, UNKNOWN shown as such)
 *   4. WHAT DEPENDS ON IT  (dependencies: neighbours, load path, change impact)
 *
 * This file holds ZERO knowledge about the rock anchor (or any detail): every
 * label, verdict, rule and neighbour is read from the payload the compiler
 * emitted (see rendering/inspector.py). A family the compiler never analysed
 * arrives verdict "UNKNOWN — NOT ANALYSED" and renders as an open question.
 *
 * The three.js GLB plumbing (decode, node-name sanitize/resolve, raycast pick,
 * metalness=0, camera framing) reuses the approach proven in web_viewer/
 * viewer.js — the interaction model here (a persistent side panel + selection +
 * graph navigation) is different enough that this is a sibling, not a fork.
 */
(function () {
  "use strict";

  var THREE = window.THREE;

  function hasWebGL() {
    try {
      var c = document.createElement("canvas");
      return !!(window.WebGLRenderingContext &&
        (c.getContext("webgl") || c.getContext("experimental-webgl")));
    } catch (e) { return false; }
  }
  var CAPABLE = !!THREE && typeof THREE.GLTFLoader === "function" &&
    hasWebGL() && typeof DecompressionStream !== "undefined" &&
    typeof Response !== "undefined";

  function ready(fn) {
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  // --- tiny DOM helper ------------------------------------------------------
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") e.className = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) {
      if (c == null) return;
      e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return e;
  }
  function verdictClass(v) {
    var s = String(v || "").toUpperCase();
    if (s.indexOf("FAIL") === 0) return "fail";
    if (s.indexOf("PASS") === 0) return "pass";
    return "unknown";
  }

  ready(function () {
    var root = document.getElementById("inspector-root");
    if (!root) return;
    var slug = root.getAttribute("data-slug");
    var dataEl = document.getElementById("inspector-data-" + slug);
    if (!dataEl) return;
    var payload = JSON.parse(dataEl.textContent);
    var app = new Inspector(root, payload, slug);
    app.mount();
  });

  function Inspector(root, payload, slug) {
    this.root = root;
    this.payload = payload;
    this.slug = slug;
    this.selected = null;
    this.partNodes = {};   // name -> {meshes:[]}
    this.model = null;
  }

  Inspector.prototype.mount = function () {
    var self = this;
    var p = this.payload;

    // ---- shell -------------------------------------------------------------
    this.stage = el("div", { class: "ix-stage" });
    this.panel = el("div", { class: "ix-panel" });
    var shell = el("div", { class: "ix-shell" }, [this.stage, this.panel]);
    this.root.appendChild(shell);

    // stage header / footer
    var analysed = p.coverage.analysed_families;
    var unknown = p.coverage.unknown_families;
    this.stage.appendChild(el("div", { class: "ix-stage-head" }, [
      el("div", {}, [
        el("div", { class: "ix-eyebrow", text: "Inspector · compiler view" }),
        el("h1", { text: p.name }),
        el("div", { class: "ix-sub",
          text: p.part_order.length + " components · " + analysed +
                " families analysed · " + unknown + " NOT analysed" }),
      ]),
    ]));
    var themeBtn = el("button", {
      class: "ix-theme-btn", type: "button", text: "◐ theme",
      onclick: function () { self.toggleTheme(); },
    });
    this.stage.appendChild(el("div", { class: "ix-stage-foot" }, [
      el("span", { text: "drag orbit · scroll zoom · click a part to inspect" }),
      themeBtn,
    ]));

    this.renderEmptyPanel();

    if (!CAPABLE) { this.mountFallback(); return; }
    var loading = el("div", { class: "ix-loading", text: "Loading model…" });
    this.stage.appendChild(loading);
    this.loadModel().then(function () {
      loading.remove();
    }).catch(function (err) {
      loading.remove();
      console.error("[inspector] model load failed", err);
      self.mountFallback();
    });
  };

  Inspector.prototype.mountFallback = function () {
    // No WebGL: the panel is still a fully usable index into the payload.
    var self = this;
    var list = el("div", { class: "ix-fallback" }, [
      el("div", {}, [
        el("p", { text: "3D model unavailable in this browser — pick a component:" }),
        el("div", { class: "ix-fallback-list" },
          this.payload.part_order.map(function (name) {
            return el("div", {}, [el("a", {
              href: "#", class: "ix-neighbor-name", text: name,
              onclick: function (e) { e.preventDefault(); self.selectPart(name); },
            })]);
          })),
      ]),
    ]);
    this.stage.appendChild(list);
  };

  Inspector.prototype.toggleTheme = function () {
    var cur = document.documentElement.getAttribute("data-theme");
    var next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    if (this.refreshHighlight) this.refreshHighlight();
  };

  // ======================================================================= //
  // three.js model
  // ======================================================================= //
  Inspector.prototype.decodeGlb = function (b64) {
    var bin = atob(b64.trim());
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var stream = new Blob([bytes]).stream()
      .pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).arrayBuffer();
  };

  Inspector.prototype.loadModel = function () {
    var self = this;
    var glbEl = document.getElementById("inspector-glb-" + this.slug);
    if (!glbEl) return Promise.reject(new Error("no glb payload"));
    return this.decodeGlb(glbEl.textContent).then(function (buf) {
      return new Promise(function (resolve, reject) {
        new THREE.GLTFLoader().parse(buf, "", function (gltf) {
          try { self.buildScene(gltf); resolve(); }
          catch (e) { reject(e); }
        }, reject);
      });
    });
  };

  Inspector.prototype.cssVar = function (name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v || "").trim() || fallback;
  };

  Inspector.prototype.buildScene = function (gltf) {
    var self = this;
    var stage = this.stage;
    var canvas = el("canvas", { class: "ix-canvas" });
    stage.insertBefore(canvas, stage.firstChild);

    var w = stage.clientWidth || 800, h = stage.clientHeight || 600;
    var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    renderer.setClearColor(0x000000, 0);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(38, w / h, 0.1, 200000);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a929e, 1.1));
    var key = new THREE.DirectionalLight(0xffffff, 0.8); key.position.set(1, -1.4, 1.2); scene.add(key);
    var fill = new THREE.DirectionalLight(0xffffff, 0.3); fill.position.set(-1, 1, 0.4); scene.add(fill);

    var model = gltf.scene; scene.add(model); this.model = model;
    // glTF default metalness=1 renders black without an env map — matte it.
    model.traverse(function (o) {
      if (!o.isMesh || !o.material) return;
      var mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach(function (m) {
        if ("metalness" in m) m.metalness = 0.0;
        if ("roughness" in m) m.roughness = 0.7;
        m.needsUpdate = true;
      });
    });

    // Resolve GLB node name -> payload part key through three's sanitizer.
    var sanitize = (THREE.PropertyBinding && THREE.PropertyBinding.sanitizeNodeName)
      || function (n) { return n.replace(/\s/g, "_"); };
    var bySan = {};
    this.payload.part_order.forEach(function (k) { bySan[sanitize(k)] = k; });
    function resolvePart(name) {
      if (!name) return null;
      if (self.payload.parts[name]) return name;
      if (bySan[name]) return bySan[name];
      var m = name.match(/^(.*)_\d+$/);
      if (m && bySan[m[1]]) return bySan[m[1]];
      return null;
    }
    (function stamp(o, inh) {
      var pn = inh || resolvePart(o.name);
      if (pn) o.userData.partName = pn;
      for (var i = 0; i < o.children.length; i++) stamp(o.children[i], pn);
    })(model, null);
    model.traverse(function (o) {
      var pn = o.userData.partName;
      if (!pn) return;
      var e = self.partNodes[pn] || (self.partNodes[pn] = { meshes: [] });
      if (o.isMesh) e.meshes.push(o);
    });

    // frame
    var box = new THREE.Box3().setFromObject(model);
    var center = box.getCenter(new THREE.Vector3());
    var size = box.getSize(new THREE.Vector3());
    var maxDim = Math.max(size.x, size.y, size.z) || 1;
    var dist = (maxDim / (2 * Math.tan((camera.fov * Math.PI) / 360))) * 1.6;
    camera.position.copy(center.clone().add(new THREE.Vector3(1, -1, 0.6).normalize().multiplyScalar(dist)));
    camera.near = dist / 100; camera.far = dist * 100; camera.updateProjectionMatrix();

    var controls = new THREE.OrbitControls(camera, canvas);
    controls.target.copy(center);
    controls.enableDamping = true; controls.dampingFactor = 0.09;
    controls.update();

    this.HL = new THREE.Color(this.cssVar("--acc", "#4c8dff")).getHex();
    this.refreshHighlight = function () {
      self.HL = new THREE.Color(self.cssVar("--acc", "#4c8dff")).getHex();
      if (self.selected) self.setEmissive(self.selected, self.HL);
    };

    // pick
    var raycaster = new THREE.Raycaster();
    var pointer = new THREE.Vector2();
    var pending = null;
    function pickAt(sx, sy) {
      pointer.x = (sx / stage.clientWidth) * 2 - 1;
      pointer.y = -(sy / stage.clientHeight) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      var hits = raycaster.intersectObject(model, true);
      for (var i = 0; i < hits.length; i++) {
        var o = hits[i].object;
        while (o) { if (o.userData && o.userData.partName) return o.userData.partName; o = o.parent; }
      }
      return null;
    }
    var downAt = null;
    canvas.addEventListener("pointerdown", function (e) {
      var r = canvas.getBoundingClientRect();
      downAt = { x: e.clientX - r.left, y: e.clientY - r.top };
    });
    canvas.addEventListener("pointerup", function (e) {
      if (!downAt) return;
      var r = canvas.getBoundingClientRect();
      var ux = e.clientX - r.left, uy = e.clientY - r.top;
      var moved = Math.abs(ux - downAt.x) + Math.abs(uy - downAt.y);
      downAt = null;
      if (moved > 5) return;             // a drag-orbit, not a click
      var part = pickAt(ux, uy);
      if (part) self.selectPart(part);
    });
    canvas.addEventListener("pointermove", function (e) {
      var r = canvas.getBoundingClientRect();
      pending = { x: e.clientX - r.left, y: e.clientY - r.top };
    });

    function resize() {
      var W = stage.clientWidth, H = stage.clientHeight;
      if (!W || !H) return;
      renderer.setSize(W, H, false);
      camera.aspect = W / H; camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize);
    var mql = window.matchMedia("(prefers-color-scheme: dark)");
    if (mql.addEventListener) mql.addEventListener("change", function () { self.refreshHighlight(); });
    new MutationObserver(function () { self.refreshHighlight(); })
      .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    function frame() {
      requestAnimationFrame(frame);
      if (pending) {
        var pk = pickAt(pending.x, pending.y); pending = null;
        canvas.style.cursor = pk ? "pointer" : "grab";
      }
      controls.update();
      renderer.render(scene, camera);
    }
    frame();
  };

  Inspector.prototype.setEmissive = function (name, hex) {
    var e = this.partNodes[name];
    if (!e) return;
    e.meshes.forEach(function (m) {
      if (!m.userData._clone) { m.material = m.material.clone(); m.userData._clone = true; }
      if (m.material.emissive) m.material.emissive.setHex(hex);
    });
  };

  Inspector.prototype.highlightOnly = function (name) {
    if (this.selected && this.selected !== name) this.setEmissive(this.selected, 0x000000);
    this.selected = name;
    if (name && this.HL != null) this.setEmissive(name, this.HL);
  };

  // ======================================================================= //
  // The panel — the four questions, rendered from the payload
  // ======================================================================= //
  Inspector.prototype.selectPart = function (name) {
    var part = this.payload.parts[name];
    if (!part) { console.warn("[inspector] no payload part", name); return; }
    this.highlightOnly(name);
    this.renderPanel(part);
    this.panel.scrollTop = 0;
  };

  Inspector.prototype.renderEmptyPanel = function () {
    this.panel.innerHTML = "";
    this.panel.appendChild(el("div", { class: "ix-panel-empty" }, [
      el("div", { class: "ix-empty-mark", text: "⌖" }),
      el("p", { html: "Click any component in the model to inspect it — what it " +
        "is, why the compiler placed it, how it was verified, and what depends on it." }),
      this.coverageStrip(this.payload.coverage.families, null,
        "Assembly-wide coverage"),
      el("div", { class: "ix-standing", html:
        "<strong>" + esc(this.payload.coverage.standing_note) + "</strong>" }),
    ]));
  };

  Inspector.prototype.renderPanel = function (part) {
    var self = this;
    var d = part.descriptor;
    this.panel.innerHTML = "";

    // sticky head
    this.panel.appendChild(el("div", { class: "ix-part-head" }, [
      el("h2", { class: "ix-part-name", text: part.reader_name || part.name }),
      el("div", { class: "ix-part-type" }, [
        d.component_type + " · " + d.material,
      ]),
      el("div", { class: "ix-part-id", text: part.part_id }),
    ]));

    this.panel.appendChild(this.sec(1, "What is this", this.renderDescriptor(d)));
    this.panel.appendChild(this.sec(2, "Why is it here", this.renderProvenance(part.provenance)));
    this.panel.appendChild(this.sec(3, "How do we know it's correct", this.renderVerification(part.verification)));
    this.panel.appendChild(this.sec(4, "What depends on it", this.renderDependencies(part.dependencies)));
    this.panel.appendChild(el("div", { class: "ix-scroll-fade" }));
  };

  Inspector.prototype.sec = function (n, title, body) {
    return el("section", { class: "ix-section" }, [
      el("h2", {}, [el("span", { class: "ix-num", text: String(n) }), title]),
      body,
    ]);
  };

  // ---- 1. WHAT IS THIS -----------------------------------------------------
  Inspector.prototype.renderDescriptor = function (d) {
    var rows = [
      ["Type", d.component_type, true],
      ["Material", d.material, true],
      ["Dimensions", d.descriptor, false],
      ["BOM item", d.bom_label, false],
    ];
    var kv = el("dl", { class: "ix-kv" });
    rows.forEach(function (r) {
      kv.appendChild(el("dt", { text: r[0] }));
      kv.appendChild(el("dd", { class: r[2] ? "mono" : "", text: r[1] }));
    });
    // params
    var pkeys = Object.keys(d.params || {});
    if (pkeys.length) {
      kv.appendChild(el("dt", { text: "Parameters" }));
      var pv = el("dd", { class: "mono" });
      pv.textContent = pkeys.map(function (k) {
        return k + "=" + fmtVal(d.params[k]);
      }).join("  ");
      kv.appendChild(pv);
    }
    if (d.datums && d.datums.length) {
      kv.appendChild(el("dt", { text: "Datums" }));
      kv.appendChild(el("dd", { class: "mono", text: d.datums.join(", ") }));
    }
    var kids = [kv,
      el("div", { class: "ix-fact-meta", html:
        'authored fact <span class="ix-badge ' + esc(d.source_type) + '">' +
        esc(d.source_type) + "</span>" })];
    if (d.assumptions) {
      kids.push(el("div", { class: "ix-assume", html:
        "<strong>Assumptions:</strong> " + esc(d.assumptions) }));
    }
    return el("div", {}, kids);
  };

  // ---- 2. WHY IS IT HERE ---------------------------------------------------
  Inspector.prototype.renderProvenance = function (prov) {
    var kids = [];
    // authored
    var authored = el("div", { class: "ix-prov-group" }, [
      el("div", { class: "ix-prov-label authored" }, [
        "Authored", el("span", { class: "ix-count", text: prov.authored.length + " declarations" }),
      ]),
    ]);
    if (!prov.authored.length)
      authored.appendChild(el("div", { class: "ix-empty-note", text: "No declaration names this part directly." }));
    prov.authored.forEach(function (a) {
      authored.appendChild(el("div", { class: "ix-fact" }, [
        el("div", { class: "ix-fact-main", text: a.label }),
        el("div", { class: "ix-fact-meta", html:
          esc(a.connection_type || a.subtype || "declaration") +
          ' <span class="ix-badge ' + esc(a.source_type) + '">' + esc(a.source_type) + "</span>" }),
      ]));
    });
    kids.push(authored);

    // derived
    var derived = el("div", { class: "ix-prov-group" }, [
      el("div", { class: "ix-prov-label derived" }, [
        "Derived by the compiler", el("span", { class: "ix-count", text: prov.derived.length + " facts" }),
      ]),
    ]);
    if (!prov.derived.length)
      derived.appendChild(el("div", { class: "ix-empty-note", text: "No rule inferred a fact about this part." }));
    prov.derived.forEach(function (f) {
      derived.appendChild(el("div", { class: "ix-fact" }, [
        el("div", { class: "ix-fact-main", text: f.fact }),
        el("div", { class: "ix-fact-meta", html:
          '<span class="ix-rule">' + esc(f.rule) + "</span> · " +
          esc(f.confidence) +
          ' <span class="ix-badge ' + esc(f.source_type) + '">' + esc(f.source_type) + "</span>" }),
      ]));
    });
    kids.push(derived);

    if (prov.chain && prov.chain.length) {
      kids.push(el("div", { class: "ix-chain", text: prov.chain.join("\n") }));
    }
    return el("div", {}, kids);
  };

  // ---- 3. HOW DO WE KNOW IT'S CORRECT --------------------------------------
  Inspector.prototype.renderVerification = function (v) {
    var self = this;
    var kids = [];

    // part-scoped family verdicts (what was checked ABOUT THIS PART)
    if (v.part_families.length) {
      var fam = el("div", {});
      v.part_families.forEach(function (f) {
        fam.appendChild(el("div", { class: "ix-verdict-row" }, [
          el("span", { class: "ix-badge " + verdictClass(f.verdict), text: shortVerdict(f.verdict) }),
          el("div", { class: "ix-fam" }, [f.family,
            el("small", { text: f.note })]),
        ]));
      });
      kids.push(fam);
    }

    // the findings, each EXPLAINED (never a bare verdict) — expandable "Because"
    if (v.findings.length) {
      kids.push(el("div", { class: "ix-count-note",
        text: v.findings.length + " checks touched this part — click to see why each holds" }));
      var wrap = el("div", {});
      v.findings.forEach(function (fd) {
        var body = el("div", { class: "ix-because" }, [
          el("div", { class: "ix-because-lead", text: "Because:" }),
          el("div", { class: "ix-because-line", text: fd.explanation }),
        ]);
        // name the generator(s) — the fact or intrinsic law behind the check
        (fd.generated_by || []).forEach(function (g) {
          var line = g.kind === "derived_fact"
            ? (g.rule + " → " + g.fact + "  [" + g.source_type + "]")
            : (g.label + "  [" + (g.source_type || "intrinsic") + "]");
          body.appendChild(el("div", { class: "ix-because-line", text: line }));
        });
        var row = el("div", { class: "ix-finding" }, [
          el("div", { class: "ix-finding-head", onclick: function () {
            row.classList.toggle("open");
          } }, [
            el("span", { class: "ix-caret", text: "▸" }),
            el("span", { class: "ix-badge " + (fd.passed ? "pass" : "fail"),
              text: fd.passed ? "PASS" : "FAIL" }),
            el("span", { class: "ix-f-subject", text: fd.subject }),
            el("span", { class: "ix-f-check", text: fd.check }),
          ]),
          body,
        ]);
        wrap.appendChild(row);
      });
      kids.push(wrap);
    }

    // Represented load path (ONTOLOGY): here it is EVIDENCE for the Load-path
    // family verdict, so section 3 shows a compact reference (chain as text) and
    // points at section 4, where the full navigable box lives — the path itself
    // is a dependency, so it's rendered once, in "What depends on it".
    (v.load_paths || []).forEach(function (lp) {
      kids.push(self.loadPathRef(lp));
    });

    // the honest coverage picture: the whole assembly's seven families, so the
    // UNKNOWN ones are visible against this part too.
    kids.push(el("div", { class: "ix-count-note", text: "Assembly coverage — all families" }));
    kids.push(this.coverageStrip(this.payload.coverage.families, null, null));

    // the standing disclaimer, always.
    kids.push(el("div", { class: "ix-standing", html:
      "<strong>" + esc(v.standing_note) + "</strong>" }));
    return el("div", {}, kids);
  };

  Inspector.prototype.coverageStrip = function (families, _sel, heading) {
    var box = el("div", {});
    if (heading) box.appendChild(el("div", { class: "ix-count-note", text: heading }));
    families.forEach(function (f) {
      box.appendChild(el("div", { class: "ix-verdict-row" }, [
        el("span", { class: "ix-badge " + verdictClass(f.verdict),
          text: f.analysed ? shortVerdict(f.verdict) : "NOT ANALYSED" }),
        el("div", { class: "ix-fam" }, [f.family,
          el("small", { text: f.note })]),
      ]));
    });
    return box;
  };

  // Compact, non-duplicating reference to a load path used as EVIDENCE in
  // section 3 — the chain as plain text (not the navigable box) + a pointer to
  // section 4 where the full box lives. Keeps the represented path visible as
  // support for the Load-path verdict without re-rendering the dependency.
  Inspector.prototype.loadPathRef = function (lp) {
    var chainText = (lp.chain || []).join(" → ");
    return el("div", { class: "ix-lp-ref" }, [
      el("span", { class: "ix-badge unknown",
        text: lp.represented ? "REPRESENTED" : "BROKEN" }),
      el("span", { class: "ix-lp-ref-text", html:
        " " + esc(lp.load_class) + ": " + esc(chainText) +
        ' <span class="ix-lp-ref-see">— full path under "What depends on it"</span>' }),
    ]);
  };

  Inspector.prototype.loadPathBox = function (lp) {
    var self = this;
    var chain = el("div", { class: "ix-lp-chain" });
    (lp.chain || []).forEach(function (nodeName, i) {
      if (i) chain.appendChild(el("span", { class: "ix-lp-arrow", text: "→" }));
      chain.appendChild(el("span", {
        class: "ix-lp-node" + (nodeName === self.selected ? " current" : ""),
        text: nodeName,
        onclick: function () { if (self.payload.parts[nodeName]) self.selectPart(nodeName); },
      }));
    });
    return el("div", { class: "ix-loadpath" }, [
      el("div", { html: '<span class="ix-badge unknown">' +
        (lp.represented ? "REPRESENTED" : "BROKEN") + "</span> " +
        esc(lp.load_class) + " → ground: " + esc(lp.reached_ground) }),
      chain,
      el("div", { class: "ix-lp-note", text: lp.note }),
    ]);
  };

  // ---- 4. WHAT DEPENDS ON IT -----------------------------------------------
  Inspector.prototype.renderDependencies = function (dep) {
    var self = this;
    var kids = [];

    // construction-graph neighbours (navigable)
    var nb = el("div", {});
    if (!dep.neighbors.length)
      nb.appendChild(el("div", { class: "ix-empty-note", text: "No construction-graph neighbours." }));
    dep.neighbors.forEach(function (n) {
      var name = n.other_name;
      nb.appendChild(el("div", { class: "ix-neighbor" }, [
        el("span", { class: "ix-edge-kind", text: n.edge }),
        el("span", { class: "ix-arrow", text: n.direction === "out" ? "→" : "←" }),
        el("span", { class: "ix-neighbor-name", text: name || n.other,
          onclick: function () { if (name && self.payload.parts[name]) self.selectPart(name); } }),
      ]));
    });
    kids.push(nb);

    // load paths carried
    (dep.load_paths || []).forEach(function (lp) { kids.push(self.loadPathBox(lp)); });

    // change impact
    if (dep.invalidated_if_changed.length) {
      kids.push(el("div", { class: "ix-count-note",
        text: "If this part changed, " + dep.invalidated_if_changed.length +
              " facts/checks would need re-deriving:" }));
      var inv = el("div", {});
      // group to keep the list legible: derived_fact vs finding
      dep.invalidated_if_changed.slice(0, 12).forEach(function (it) {
        inv.appendChild(el("div", { class: "ix-invalid" }, [
          el("span", { class: "ix-edge-kind", text: it.type === "derived_fact" ? "fact" : "check" }),
          el("span", { class: "ix-inv-summary", text: it.summary }),
          el("span", { class: "ix-inv-rule", text: it.rule || it.check || "" }),
        ]));
      });
      if (dep.invalidated_if_changed.length > 12)
        inv.appendChild(el("div", { class: "ix-count-note",
          text: "+ " + (dep.invalidated_if_changed.length - 12) + " more" }));
      kids.push(inv);
    }
    return el("div", {}, kids);
  };

  // --- formatting -----------------------------------------------------------
  function fmtVal(v) {
    if (typeof v === "number") return (Math.round(v * 100) / 100).toString();
    if (Array.isArray(v)) return "[" + v.length + "]";
    return String(v);
  }
  function shortVerdict(v) {
    var s = String(v || "");
    return s.indexOf("UNKNOWN") === 0 ? "UNKNOWN" : s;
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Node/test harness hook — a no-op in the browser (no CommonJS there), it lets
  // a headless DOM shim exercise the panel-rendering path without three.js.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { Inspector: Inspector };
  }
})();
