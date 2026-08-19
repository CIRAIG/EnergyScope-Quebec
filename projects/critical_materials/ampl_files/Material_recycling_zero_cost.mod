# Loaded after Material_recycling.dat when materials_recycling_cost=False.
# Zeroes out cost/benefit terms so Recycled_material is driven purely by the
# recycling_rate technical ceiling, not by C_material. disposal_cost stays at a
# tiny nonzero value to break the otherwise-degenerate indifference and nudge the
# optimizer toward recycling up to that ceiling (negligible impact on total cost).
let {tec in TECHNOLOGIES, mat in MATERIALS} recycling_cost[tec,mat] := 0;
let {mat in MATERIALS} primary_material_cost[mat] := 0;
let {mat in MATERIALS} disposal_cost[mat] := 0.01;
