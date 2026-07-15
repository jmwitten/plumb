# DV72 Cabinet Installation Guide Design

Date: 2026-07-15

## Purpose and scope

Add a fifth, standalone document to the DV72 package that guides a field installer from an unverified wall through a securely mounted, empty cabinet. The guide stops before countertop placement, sink installation, plumbing connections, drawer installation, loading, or commissioning.

The guide is conditional coordination information until its named field, structural, product, and trade release gates are closed. It must never imply that the current model proves the wall connection, Rakks reaction distribution, or cabinet case/interface attachment.

## Reader and format

The primary reader is a competent cabinet installer or carpenter arriving with no project history. The document uses the recent DB40 consumer-manual language rather than the existing DV72 technical-sheet language:

- print-first US Letter sheets on a gray screen background;
- high-contrast black frames and large circled step numbers;
- one or two action frames per page;
- concise resource chips for people, tools, parts, and approvals;
- an unavoidable STOP sheet before any installation action;
- numbered picture keys and model-backed diagrams;
- explicit `WHY`, `VERIFY`, `STOP`, and record fields;
- page numbers, reciprocal document links, responsive screen behavior, and clean print output.

The guide remains useful on a phone, but wide technical schedules stay in the linked review, fabrication, and validation documents.

## Document sequence

The guide is limited to eight composed Letter pages and 1,500 instructional words.

1. **Cover and outcome.** Identify DV72, show the empty mounted-cabinet endpoint, state the installation hold, and link the other four documents.
2. **People, tools, products, and boundaries.** Identify accepted-plan fields for crew, equipment, handling, support, and restraint; wall-verification tools; the selected Rakks product reference; and excluded work. Unselected structural fasteners and cabinet case/interface hardware appear as release fields, never recommendations.
3. **STOP — release and field record.** Require recorded wall construction, framing/blocking, utilities, bracket revision, structural fastener schedule, cabinet case/interface detail, and responsible approvals before proceeding. No action illustration may precede this page.
4. **Lay out the wall.** Establish the model-derived finished-counter datum and the left-end, center-divider, and right-end support axes. Compare field measurements with the owner-assumed model and stop on disagreement.
5. **Install and verify the three supports.** Show the Rakks wall leg, horizontal arm, diagonal load path, and schedule-controlled fastener-location placeholder. All product and fastener instructions remain subordinate to accepted product and structural records. Verify count, spacing, projection, level, wall plane, backing, utilities, and rough-in observations without granting service-access approval.
6. **Stage and place the empty cabinet.** Require drawers, countertop, sinks, and loose components to be absent. Show an accepted handling/support/restraint-plan placeholder, protection/clearance, arm alignment, and the case relationship below and around the countertop-support arms. Cabinet mounting is governed by the accepted cabinet case/interface detail. Stop if the accepted plan cannot be followed or an observed rough-in conflict differs from its accepted record.
7. **Restrain the cabinet.** Apply only the accepted cabinet case/interface detail. Show the continuous rear rail as positioning/lateral restraint with zero gravity credit. Do not depict or name invented screws, hole patterns, temporary restraints, or connection capacity.
8. **Mounted-cabinet inspection and handoff.** Record completion acceptance, level, plumb, diagonal/square check, wall gaps, accepted-interface contact/restraint, fastener witness marks and count against the accepted schedule, cabinet restraint, observed rough-in conflict without service-access approval, deviations, release-attachment links, installer, authorized reviewer role/signature, and date. End with a hard stop before countertop, sinks, plumbing, drawers, loading, or use.

## Safety correction supersession

This design supersedes the earlier two-person-lift, temporary-support, three-support-plane, bottom-bearing, and support-contact wording. The typed Rakks arms are at the countertop underside, not at the cabinet bottom, and the actual empty-case handling method, equipment, crew, temporary support, and restraint remain unselected. Placement therefore follows only the accepted handling/support/restraint plan; the case passes below and around the countertop-support arms; and mounting/restraint follows only the accepted cabinet case/interface detail. The required illustration may show the accepted-plan placeholder, protection/clearance, arm alignment, and case relationship, but it must not invent people, equipment, connections, or cabinet-bearing planes.

## Model and authority integration

The installation guide is a projection of the same typed DV72 model used by the other documents. It consumes:

- assumed-site wall, framing, backing, and rough-in facts;
- vanity geometry and finished-counter datum;
- three `SupportEnvelope` positions and manufacturer reference;
- the rear rail's `positioning_and_lateral_only` role and zero gravity credit;
- service/plumbing and drawer envelopes needed for collision warnings;
- split release findings and provenance.

Numeric dimensions, support positions, product identifiers, and authority states must be rendered from typed facts rather than duplicated literals. Mutating a source fact in tests must change or hold the corresponding guide output.

The guide adds no new structural PASS. When installation authority is held, the cover and STOP sheet remain held and every later action is labeled conditional. A document-generation audit must fail if the guide contradicts the other four documents.

## Implementation boundary

Add `dv72_installation_guide.html` to the deterministic document set and reciprocal navigation. Preserve the existing four documents and their reader scopes.

Prefer the shared instruction-page grammar established by the DB40 manuals. Port the smallest stable shared rendering units needed for Letter sheets, action frames, resource chips, STOP pages, and records; do not copy a large project-specific CSS blob or import unrelated cutting-guide behavior. DV72 diagrams may remain deterministic inline SVG so the guide does not manufacture a false photorealistic or finished 3D state.

Likely implementation files:

- `src/packs/cabinetry/double_vanity_installation_guide.py` — typed guide projection and rendering;
- `src/packs/cabinetry/double_vanity_documents.py` — five-document composition, labels, filenames, and reciprocal links;
- shared instruction-page rendering modules, only if required by the selected DB40 precedent;
- `scripts/double_vanity_documents.py` — generated inventory description;
- `tests/test_double_vanity_installation_guide.py` — guide-specific contracts;
- `tests/test_double_vanity_documents.py` — five-document closure and cross-document authority audits.

## Validation and review

Tests must establish:

- exactly five deterministic documents with reciprocal local links;
- eight or fewer composed pages and 1,500 or fewer instructional words;
- the STOP sheet precedes all action imagery;
- held authority appears on the cover and every post-gate action is conditional;
- three model-derived Rakks locations align with left end, center divider, and right end;
- the rear rail receives zero gravity credit;
- no cabinet case/interface or structural fastener is invented;
- dimensions and product facts respond to typed-model mutations;
- no machine identifiers, `file://` dependencies, missing assets, or external runtime assets;
- headless-browser PDF page count matches composed sheet count;
- desktop and 390-pixel rendering contain all content, with print pagination intact;
- the generated package passes link, authority, contradiction, and deterministic-hash audits.

After implementation, obtain an adversarial technical review and a fresh no-context installer review. Fix Critical and Important findings before pushing the branch.

## Success criteria

An installer can identify what must be approved, establish the wall/support layout, understand the Rakks load path, place and restrain the empty cabinet using an accepted connection detail, record the result, and know exactly where to stop. The guide is visually consistent with the new instruction manuals while preserving the DV72 package's honest release semantics.
