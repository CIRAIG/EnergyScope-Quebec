set MATERIALS;

# Variantes de distance (_SD/_MD/_LD/_ELD, Material_mob_family_exclusion.dat) : exclues pour eviter
# de compter deux fois la matiere, deja portee par F_new de la techno "famille".
set MOB_VARIANT_TECHS within TECHNOLOGIES default {};
set MATERIAL_TECHS := TECHNOLOGIES diff MOB_VARIANT_TECHS;

# -----------------PARAMETERS------------------------------------------------------------------------------------------------

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW]
param limit_material_year {YEARS,MATERIALS} >= 0 default 1000000000;            # [t/year]
param limit_material {MATERIALS} >= 0 default 1000000000;                       # [t]

param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [%] End-of-Life recycling rate (plafond technique de recuperation)
param recycling_cost {TECHNOLOGIES,MATERIALS} >= 0 default 0;                 # [$/t]
param disposal_cost {MATERIALS} >= 0 default 0.001;                           # [$/t] estimation generique
param primary_material_cost {MATERIALS} >= 0 default 0;                       # [$/t] cout matiere vierge evitee si recycle

# Sans signal economique (materials_recycling_cost=False) Recycled_material est indetermine pour le
# solveur ; force l'egalite avec le plafond technique.
param force_recycling_max binary default 0;                                   # [-]

# -----------------VARIABLES------------------------------------------------------------------------------------------------

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [t/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [t] cumule sur l'horizon

var Decommissioned_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;  # [t/year] materiau demantele (mecanique)
var Recycled_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] materiau recycle (decision, <= plafond)
var Disposed_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] materiau enfoui/incinere
var Recycling_benefit {YEARS,TECHNOLOGIES,MATERIALS};             # [M$/year, actualise] cout evite en recyclant
# C_material: hook dans PES_main.mod

# Banque de matiere recyclee en exces une annee (non necessaire a la demande brute de cette annee),
# mobilisable les annees suivantes -- cf. material_stock_calc / used_recycled_material_cap.
var Material_stock {YEARS,MATERIALS} >= 0;                          # [t] cumule depuis le debut de l'horizon (quand recyclage > demande brute)
var Used_recycled_material {YEARS_WND diff YEAR_ONE,MATERIALS} >= 0; # [t/year] matiere recyclee (de cette annee + banque) reellement mobilisee contre la demande brute de cette annee

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Hooks pour Constraints_recycling_technologies.mod (Approche 2), charge avant les donnees.
param recycled_material_process_total_ub {TECHNOLOGIES,MATERIALS} >= 0 default 0;  # releve a Infinity (utils.py) si actif
var Recycled_material_process_total {y in YEARS, tec in TECHNOLOGIES, mat in MATERIALS} >= 0, <= recycled_material_process_total_ub[tec,mat];  # [t/year]
var C_material_recycling_tech;                                            # [M$, actualise] -- pas de borne >=0, un procede peut etre net benefique
fix C_material_recycling_tech := 0;  # defaut quand Constraints_recycling_technologies.mod n'est pas charge
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# ---------------------------GROSS MATERIAL DEMAND------------------------------------------------------------------------------------------------------------------------------------

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5; #Demande brute par année
    # union {"2015_2020"} necessaire : sans ca, Material_content_year[YEAR_2020,*,*] (PHASE_STOP de
    # "2015_2020", jamais dans PHASE_WND/PHASE_UP_TO) n'etait couvert par aucune egalite -- variable
    # libre, cout nul, degeneree comme Used_recycled_material/Material_stock avant leur fix. Masque
    # quand limit_material_year est serre (materials_limit=True, la clampe pres de 0 par faisabilite,
    # pas par calcul), mais explose a la valeur par defaut (1e9) sinon -- voir material_content_year_limit.

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;#Demande brute totale

# ---------------------------DECOMMISSIONED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Matériau décommssionée par année
subject to decommissioned_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in MATERIAL_TECHS, mat in MATERIALS}:
    Decommissioned_material[y_decom,tec,mat] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec]
        + sum {p_built in AGE[tec,p_decom] diff {"STILL_IN_USE"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_old[p_decom,tec]
    );

# ---------------------------RECYCLED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Calcul de ce qu'on recycle
subject to recycled_material_max {y in YEARS_WND diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    Recycled_material[y,tec,mat] <= recycling_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

#Force au maxium du potentiel de recyclage
subject to recycled_material_forced_max {y in YEARS_WND diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    force_recycling_max * Recycled_material[y,tec,mat]
    >= force_recycling_max * recycling_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

# ---------------------------DISPOSED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Calcul de ce qu'on dispose
subject to disposed_material_calc {y in YEARS_WND diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    Disposed_material[y,tec,mat] = Decommissioned_material[y,tec,mat] - Recycled_material[y,tec,mat] - Recycled_material_process_total[y,tec,mat];

# ---------------------------NET DEMAND / USED RECYCLED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Demande nette = demande brute - Used_recycled_material, plafonne (used_recycled_material_cap) a la demande brute : jamais negative, l'exces est banque (Material_stock) plutot que compte en negatif.
subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in MATERIAL_TECHS} Material_content_year[y,tec,mat] - Used_recycled_material[y,mat] <= limit_material_year[y,mat];

subject to used_recycled_material_cap {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    Used_recycled_material[y,mat] <= sum {tec in MATERIAL_TECHS} Material_content_year[y,tec,mat];

# ---------------------------MATERIAL STOCK------------------------------------------------------------------------------------------------------------------------------------

# Calcul stock de matériau
subject to material_stock_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, mat in MATERIALS}:
    Material_stock[y,mat] = sum {p2 in PHASE_WND union PHASE_UP_TO, y2 in PHASE_STOP[p2] diff YEAR_ONE : ord(p2,PHASE) <= ord(p,PHASE)}
        (sum {tec in MATERIAL_TECHS} (Recycled_material[y2,tec,mat] + Recycled_material_process_total[y2,tec,mat]) - Used_recycled_material[y2,mat]);

# ---------------------------CUMULATIVE AVAILABILITY LIMIT------------------------------------------------------------------------------------------------------------------------------------

# Max de disponibilité -- Used_recycled_material (pas Recycled_material) : seule la matiere reellement
# mobilisee contre la demande remplace de la matiere vierge ; celle recyclee mais encore banquee
# (Material_stock) n'a pas encore evite d'extraction.
subject to material_content_limit {mat in MATERIALS}:
    sum {tec in MATERIAL_TECHS} Material_content[tec,mat]
    - sum {y in YEARS_WND diff YEAR_ONE} Used_recycled_material[y,mat] * 5 <= limit_material[mat];

# ------------Equation for cost of recycling----------------------------------------------

# Calcul du bénéfice de recyclage
subject to recycling_benefit_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    Recycling_benefit[y,tec,mat] = actualisation_factor[p,y] * (primary_material_cost[mat] + disposal_cost[mat] - recycling_cost[tec,mat]) * Recycled_material[y,tec,mat] / 1e6;

unfix C_material;  # PES_main.mod le fixe a 0 par defaut
subject to material_cost_calc:
    C_material = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}
        actualisation_factor[p,y] *
        (recycling_cost[tec,mat] * Recycled_material[y,tec,mat]
         - primary_material_cost[mat] * Recycled_material[y,tec,mat]
         + disposal_cost[mat] * Disposed_material[y,tec,mat]) * 5 / 1e6
        + C_material_recycling_tech
        + sum {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS} 0.001 * Material_stock[y,mat] * 5 / 1e6; # Cout pour utilisation de stock pour 'forcer' l'utilisation de la matière recyclé
