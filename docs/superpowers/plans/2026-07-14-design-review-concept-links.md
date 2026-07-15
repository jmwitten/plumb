# Design-Review Concept Example Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit, deterministic precedent-example links beneath every concept in the developer design-review report.

**Architecture:** The report renderer will derive each concept's examples from the union of its feature `precedent_refs`, then order matching sources by the canonical `doc.precedents` sequence. No schema or fingerprint data changes; the generated caddy HTML is regenerated from the same YAML record.

**Tech Stack:** Python 3.12, frozen dataclasses, deterministic HTML strings, pytest.

## Global Constraints

- URLs, titles, publishers, source kinds, and access dates remain single-sourced in `DesignReviewDoc.precedents`.
- Do not add concept-level example fields to the YAML schema.
- Do not embed remote images, scripts, styles, or third-party content.
- Concepts with no referenced precedent must render an explicit no-direct-precedent message.
- The selection fingerprint, approval state, customer manual, and caddy geometry must remain unchanged.

---

### Task 1: Render explicit examples for every concept

**Files:**
- Modify: `src/design_review/report.py`
- Modify: `tests/test_design_review_report.py`
- Modify: `tests/test_caddy_design_review.py`
- Regenerate: `outputs/design-reviews/armchair_caddy.html`

**Interfaces:**
- Consumes: `DesignReviewDoc.precedents`, `Concept.features`, and `ConceptFeature.precedent_refs`.
- Produces: `_concept_precedents(doc: DesignReviewDoc, concept: Concept) -> tuple[Precedent, ...]` and an `Examples` subsection in `render_design_review_html()`.

- [ ] **Step 1: Write failing generic report tests**

Add `replace` to the imports in `tests/test_design_review_report.py`, then extend the deterministic report test:

```python
assert "<h4>Examples</h4>" in first
assert "View example: Commercial three-panel saddle" in first
assert "Example Furniture · commercial_product" in first
```

Add a no-direct-precedent regression:

```python
def test_report_names_concepts_without_direct_precedent():
    doc = load_design_review_file(FIXTURE)
    concept = doc.concepts[0]
    features = tuple(
        replace(feature, precedent_refs=()) for feature in concept.features
    )
    concept = replace(concept, features=features)
    changed = replace(doc, concepts=(concept,) + doc.concepts[1:])

    rendered = render_design_review_html(
        changed, validate_design_review(changed)
    )
    start = rendered.index("<code>concept_a</code>")
    end = rendered.index("<code>concept_b</code>")
    section = rendered[start:end]

    assert (
        "No direct precedent identified; review the novelty/deviation "
        "basis below."
    ) in section
```

- [ ] **Step 2: Write the failing caddy concept-link test**

Extend `test_generated_caddy_report_is_developer_facing_and_retains_provenance()`:

```python
start = html.index("<code>reinforced_miter</code>")
end = html.index("<code>rabbet_and_dowel</code>")
reinforced = html[start:end]
assert "View example: DIY Sofa Arm Table" in reinforced
assert "https://www.loveandrenovations.com/sofa-arm-table/" in reinforced
assert "View example: Sofa Armrest Table" in reinforced
assert (
    "https://www.woodworkersjournal.com/project-sofa-armrest-table/"
    in reinforced
)
```

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_design_review_report.py \
  tests/test_caddy_design_review.py
```

Expected: failures because the concept `Examples` subsection and explicit link labels do not exist.

- [ ] **Step 4: Implement the deterministic source lookup**

In `src/design_review/report.py`, import `Concept` and `Precedent`, then add:

```python
def _concept_precedents(
    doc: DesignReviewDoc,
    concept: Concept,
) -> tuple[Precedent, ...]:
    referenced = {
        precedent_ref
        for feature in concept.features
        for precedent_ref in feature.precedent_refs
    }
    return tuple(
        source for source in doc.precedents if source.id in referenced
    )
```

This deliberately orders links by `doc.precedents` and collapses repeated feature references through the set.

- [ ] **Step 5: Render the Examples subsection**

Immediately after each concept summary, append:

```python
lines.append("<h4>Examples</h4>")
examples = _concept_precedents(doc, concept)
if examples:
    lines.append('<ul class="concept-examples">')
    lines.extend(
        f'<li><a href="{_e(source.url)}">View example: '
        f'{_e(source.title)}</a> — {_e(source.publisher)} · '
        f'{_e(source.kind)}</li>'
        for source in examples
    )
    lines.append("</ul>")
else:
    lines.append(
        "<p>No direct precedent identified; review the novelty/deviation "
        "basis below.</p>"
    )
```

Then append the existing architecture-signature table. Continue using `_e()` for every source value.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_design_review_report.py \
  tests/test_caddy_design_review.py \
  tests/test_design_review_validation.py
```

Expected: all tests pass; validation behavior and fingerprints remain unchanged.

- [ ] **Step 7: Regenerate and inspect the caddy report**

Run:

```bash
.venv/bin/python -m detailgen.design_review report \
  details/armchair_caddy.design-review.yaml \
  --output outputs/design-reviews/armchair_caddy.html
```

Verify in the rendered page:

- `reinforced_miter` visibly links Love & Renovations and Woodworker's Journal.
- `concealed_pocket_screw_or_bracket` visibly links Kreg and Full Hearted Home.
- The current double-wall concept does not invent support for its full-depth rails; its unsupported feature still reads `precedents: none` and remains in the deviation section.
- Production promotion and delivery remain `BLOCKED`.

- [ ] **Step 8: Run the targeted checkpoint suite**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_design_review_schema.py \
  tests/test_design_review_validation.py \
  tests/test_design_review_gate.py \
  tests/test_design_review_report.py \
  tests/test_design_review_integration.py \
  tests/test_caddy_design_review.py
git diff --check
```

Expected: all tests pass and whitespace validation reports no errors.

- [ ] **Step 9: Commit and push the report checkpoint**

```bash
git add src/design_review/report.py \
  tests/test_design_review_report.py \
  tests/test_caddy_design_review.py
git add -f outputs/design-reviews/armchair_caddy.html
git commit -m "feat: link concept precedent examples"
git push
```

Expected: the remote feature branch advances; no merge or delivery approval is created.
