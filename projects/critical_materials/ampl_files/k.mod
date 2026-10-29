# Approche K : au plus K_relax materiaux voient leur limite annuelle relachee (Relax_material, grand M par annee et materiau).
# A charger avec Material_bigM.dat (run_build_bigM.py) : extra_files=['.../ampl_files/k.mod', '.../ampl_files/Material_bigM.dat']
let K_relax := 1;

# Candidats au relachement : seuls les materiaux dont la limite est serree dans 1_baseline_limits03_free (net >= 99.9 % de la limite
# au moins une annee) peuvent faire baisser le cout ; relacher une limite non serree ne change rien. Les autres Relax_material sont
# fixes a 0, ce qui retire leurs binaires du MIP (6 au lieu de 41). Pour K >= 2, ajouter les materiaux qui deviennent serres apres un
# premier relachement (chaine sequentielle : Li, Nd, Pr, Tb, Cu).
fix {m in MATERIALS diff {'Dy','Pt','Ag','Ge','In','Te'}} Relax_material[m] := 0;
