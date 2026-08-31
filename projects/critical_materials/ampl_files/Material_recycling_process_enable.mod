# Loaded only when materials_recycling_process=True, right after Material_recycling_process.dat in
# mod_2_path -- by then TECHNOLOGIES/MATERIALS are populated (QC_data.dat/out_techs.dat already loaded),
# so this imperative `let` can safely enumerate them (Constraints.mod itself loads pre-data, in mod_1_path,
# where an indexed fix/let would fail with "no data for set..."). Releases Recycled_material_process_total's
# upper bound (0 by default, see Constraints.mod) so Constraints_recycling_technologies.mod's own equality
# (recycled_material_process_total_calc) can actually drive its value.
let {tec in TECHNOLOGIES, mat in MATERIALS} recycled_material_process_total_ub[tec,mat] := Infinity;
