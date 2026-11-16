# Neodymium is the only constrained material: the annual limits of all the other materials are set to Infinity
# (those of Material_limits.dat, loaded before this file, remain for Nd).
# To load after Material_limits.dat: extra_files=['.../ampl_files/Material_limits_Nd_only.mod']
let {y in YEARS, m in MATERIALS diff {'Nd'}} limit_material_year[y,m] := Infinity;
