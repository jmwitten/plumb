# STEPDOC +process research — adhesive cure vocabulary

Date: 2026-07-13

Scope: external installation guidance used to bound the first process event
(`cure`) and the caddy's authored cure-before-screws constraint. This is a
research record, not a substitute for the selected product label.

## Primary sources checked

- Titebond Original Wood Glue product data:
  https://www.titebond.com/print/product/d4d28015-603f-4dfc-a7d9-f684acc71207
- Titebond Wood Glues brochure:
  https://www.titebond.com/downloads/literature/glues/FF1040_Wood_Glues_Brochure.pdf
- Titebond application/FAQ guidance:
  https://titebond.com/resources/use/glues
- Gorilla Wood Glue official instructions:
  https://gorillatough.com/product/gorilla-wood-glue
- Kreg Basic Cabinetmaking booklet:
  https://www.kregtool.com/on/demandware.static/-/Library-Sites-RefArchSharedLibrary/default/dwf451dc95/project-plan/basic-cabinetmaking-booklet-101B01D.pdf
- Rockler, Building Upper Kitchen Cabinets:
  https://www.rockler.com/learn/building-upper-kitchen-cabinets
- WOOD Magazine, driving screws after glue dries:
  https://www.woodmagazine.com/drills/drive-screws-after-the-glue-dries-3

## Findings that constrain the model

1. Preparation, spread, open/assembly time, clamp time, and full cure are
   product- and condition-dependent. Titebond Original publishes a roughly
   4–6 minute open time, 10–15 minute total assembly time, 30–60 minute clamp
   time for unstressed joints at 70°F/50% RH, and no stress for 24 hours;
   Gorilla publishes 20–30 minutes clamped and 24 hours cure. Those numbers
   must not become generic language facts.
2. The stable cross-product fact is order: make the bond, maintain the
   required clamp/fixture state, and do not treat the cure as complete until
   the selected adhesive label's stated full-cure/full-strength condition is
   met under the actual shop conditions.
3. There is no universal manufacturer rule that cabinet screws are always
   driven before or after cure. Kreg/Rockler examples drive mechanical
   fasteners during wet glue; WOOD shows a workflow where screws follow the
   dried glue-up. Therefore the caddy's cure-before-side-screws sequence is an
   authored project strategy with a required `why:`, not a global Glued rule.
4. The first increment needs only one open-tagged process kind, `cure`, plus
   typed source/target order constraints. Timers, humidity/temperature
   calculations, adhesive families, clamp-pressure analysis, and bond
   capacity stay explicitly outside this increment.

## Caddy interpretation

- Each `glued` rail-to-top connection derives a bond/install event followed
  by its own cure event.
- Each rail-to-side screw connection explicitly depends on the corresponding
  rail-to-top cure, with authored provenance explaining that the cured rails
  establish and preserve the registration datum before the side boards are
  attached.
- Reader text says “per the selected adhesive label” and discloses that no
  generic duration or cure-condition calculation is represented.
- Glue and clamps remain consumable/tool roles, not geometry/BOM parts in this
  increment.
