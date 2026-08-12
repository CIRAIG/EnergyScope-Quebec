set MATERIALS;

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW]
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;            # [t/year]
param limit_material {MATERIALS} >= 0 default Infinity;                       # [t]

param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [-] plafond technique de recuperation
param collection_rate {YEARS,TECHNOLOGIES} >= 0, <= 1 default 1;              # [-] plafond de collecte
param recycling_cost {TECHNOLOGIES,MATERIALS} >= 0 default 0;                 # [$/t] cout economique du recyclage
param disposal_cost {MATERIALS} >= 0 default 0.01;                            # [$/t] cout economique enfouissement/incineration

# Cible de recycled_material_scenario (egalite, active si follow_scenario=1) -- cf. plus bas.
param recycling_scenario_share {YEARS,MATERIALS} >= 0, <= 1 default 0;
param follow_scenario binary default 0;

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [kt/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [kt] cumule sur l'horizon

var Decommissioned_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;  # [kt/year] materiau demantele (mecanique)
var Recycled_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [kt/year] materiau recycle (decision, <= plafond)
var Disposed_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [kt/year] materiau enfoui/incinere
# C_material: declare dans QC_es_pathway.mod / shared/model/QC_es_main.mod (extension hook)

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5;

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;

# Nette de Recycled_material, agrege par materiau (fongible entre technos, pas par techno d'origine)
subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat]
    - sum {tec in TECHNOLOGIES} Recycled_material[y,tec,mat] <= limit_material_year[y,mat];

# Relachee pour l'instant (demande explicite) -- decommenter pour reactiver.
#subject to net_demand_nonneg {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
#    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat]
#    - sum {tec in TECHNOLOGIES} Recycled_material[y,tec,mat] >= 0;

subject to material_content_limit {mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content[tec,mat]
    - sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES} Recycled_material[y,tec,mat] * 5 <= limit_material[mat];

# F_decom[p_decom,p_built,tec]: p_built inclut "2015_2020" (parc pre-horizon, cf. QC_es_pathway.mod)
# F_old[p_decom,tec]: millesime de construction donne par AGE[tec,p_decom], pas un indice de la variable
subject to decommissioned_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES, mat in MATERIALS}:
    Decommissioned_material[y_decom,tec,mat] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec]
        + sum {p_built in AGE[tec,p_decom] diff {"STILL_IN_USE"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_old[p_decom,tec]
    );

# Decision : combien recycler, plafonne par collection_rate*recycling_rate (le reste va a Disposed_material)
subject to recycled_material_max {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycled_material[y,tec,mat] <= collection_rate[y,tec] * recycling_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

subject to disposed_material_calc {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Disposed_material[y,tec,mat] = Decommissioned_material[y,tec,mat] - Recycled_material[y,tec,mat];

# Egalite (pas un plancher) si follow_scenario=1, sinon degenere en 0=0 (non contraignante) et seul
# recycled_material_max reste actif. Restreint aux technos avec recycling_rate>0 -- sinon ca se dilue
# dans le Decommissioned_material des technos non mappees (ex: Cu/Ni presents dans la prod electrique
# sans donnee RR_) et devient irrealisable malgre le clip de recycling_scenario_share (rr_build_table).
subject to recycled_material_scenario {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    follow_scenario * sum {tec in TECHNOLOGIES : recycling_rate[y,tec,mat] > 0} Recycled_material[y,tec,mat]
    = follow_scenario * recycling_scenario_share[y,mat] * sum {tec in TECHNOLOGIES : recycling_rate[y,tec,mat] > 0} Decommissioned_material[y,tec,mat];

subject to material_cost_calc:
    C_material = sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}
        (recycling_cost[tec,mat] * Recycled_material[y,tec,mat] + disposal_cost[mat] * Disposed_material[y,tec,mat]) * 5 * 1000;
        # *1000 : Recycled_material/Disposed_material sont en [kt], recycling_cost/disposal_cost en [$/t]
