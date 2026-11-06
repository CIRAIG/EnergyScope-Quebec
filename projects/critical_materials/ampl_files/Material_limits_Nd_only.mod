# Le neodyme est le seul materiau contraint : les limites annuelles de tous les autres materiaux passent a Infinity
# (celles de Material_limits.dat, chargees avant ce fichier, restent pour le Nd).
# A charger apres Material_limits.dat : extra_files=['.../ampl_files/Material_limits_Nd_only.mod']
let {y in YEARS, m in MATERIALS diff {'Nd'}} limit_material_year[y,m] := Infinity;
