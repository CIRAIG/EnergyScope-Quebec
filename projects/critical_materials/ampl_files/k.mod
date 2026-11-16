# K approach: at most K_relax materials get their annual limit relaxed (Relax_material, big M per year and material).
# To load with Material_bigM.dat (run_build_bigM.py): extra_files=['.../ampl_files/k.mod', '.../ampl_files/Material_bigM.dat']
let K_relax := 1;

# Candidates for relaxation: only the materials whose limit is tight in 1_baseline_limits03_free (net >= 99.9 % of the limit
# at least one year) can lower the cost; relaxing a limit that is not tight changes nothing. The other Relax_material are
# fixed to 0, which removes their binaries from the MIP (6 instead of 41). For K >= 2, add the materials that become tight after a
# first relaxation (sequential chain: Li, Nd, Pr, Tb, Cu).
fix {m in MATERIALS diff {'Dy','Pt','Ag','Ge','In','Te'}} Relax_material[m] := 0;
