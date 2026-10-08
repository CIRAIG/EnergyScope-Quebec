# Parts de marche fixes des sous-technologies (optionnel, desactive par defaut): run_pathway(..., extra_files=['.../Subtechs_market_share.mod'])
# --- TEMPORARY: fixed market-share split of new-build electricity-gen sub-techs (JRC 2020
# report: "Raw materials demand for wind and solar PV technologies in the transition towards
# a decarbonised energy system", https://data.europa.eu/doi/10.2760/160859). Delete this whole
# block (down to the closing marker) once real per-subtech costs exist and the optimizer should
# choose the mix itself -- each sub-tech is otherwise a fully independent technology with no
# other link to its siblings, so removing this block alone is enough to let the optimizer
# pick the mix freely.
# Values interpolated the same way mi_pipeline.aggregate.YEAR_TO_DECADES already does for the
# material-intensity pipeline (YEAR_2025 = average of decade 2020 and 2030, etc.); each family's
# shares sum to 1.0 per year. NEW_WIND_ONSHORE and PV_GROUND reuse the same underlying hardware
# mix as WIND_ONSHORE/PV_ROOF (confirmed identical in the source data).

param subtech_share {YEARS, TECHNOLOGIES} >= 0, <= 1 default 0;

let subtech_share['YEAR_2020','WIND_ONSHORE_DD_EESG'] := 0.060317 ;
let subtech_share['YEAR_2020','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.603175 ;
let subtech_share['YEAR_2020','WIND_ONSHORE_DD_PMSG'] := 0.188889 ;
let subtech_share['YEAR_2020','WIND_ONSHORE_GB_PMSG'] := 0.147619 ;
let subtech_share['YEAR_2025','WIND_ONSHORE_DD_EESG'] := 0.042064 ;
let subtech_share['YEAR_2025','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.600794 ;
let subtech_share['YEAR_2025','WIND_ONSHORE_DD_PMSG'] := 0.197619 ;
let subtech_share['YEAR_2025','WIND_ONSHORE_GB_PMSG'] := 0.159524 ;
let subtech_share['YEAR_2030','WIND_ONSHORE_DD_EESG'] := 0.023810 ;
let subtech_share['YEAR_2030','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.598413 ;
let subtech_share['YEAR_2030','WIND_ONSHORE_DD_PMSG'] := 0.206349 ;
let subtech_share['YEAR_2030','WIND_ONSHORE_GB_PMSG'] := 0.171429 ;
let subtech_share['YEAR_2035','WIND_ONSHORE_DD_EESG'] := 0.019048 ;
let subtech_share['YEAR_2035','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.576191 ;
let subtech_share['YEAR_2035','WIND_ONSHORE_DD_PMSG'] := 0.220635 ;
let subtech_share['YEAR_2035','WIND_ONSHORE_GB_PMSG'] := 0.184127 ;
let subtech_share['YEAR_2040','WIND_ONSHORE_DD_EESG'] := 0.014286 ;
let subtech_share['YEAR_2040','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.553968 ;
let subtech_share['YEAR_2040','WIND_ONSHORE_DD_PMSG'] := 0.234921 ;
let subtech_share['YEAR_2040','WIND_ONSHORE_GB_PMSG'] := 0.196825 ;
let subtech_share['YEAR_2045','WIND_ONSHORE_DD_EESG'] := 0.007143 ;
let subtech_share['YEAR_2045','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.528484 ;
let subtech_share['YEAR_2045','WIND_ONSHORE_DD_PMSG'] := 0.249961 ;
let subtech_share['YEAR_2045','WIND_ONSHORE_GB_PMSG'] := 0.214413 ;
let subtech_share['YEAR_2050','WIND_ONSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2050','WIND_ONSHORE_GB_DFIG_SCIG'] := 0.503000 ;
let subtech_share['YEAR_2050','WIND_ONSHORE_DD_PMSG'] := 0.265000 ;
let subtech_share['YEAR_2050','WIND_ONSHORE_GB_PMSG'] := 0.232000 ;
let subtech_share['YEAR_2020','NEW_WIND_ONSHORE_DD_EESG'] := 0.060317 ;
let subtech_share['YEAR_2020','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.603175 ;
let subtech_share['YEAR_2020','NEW_WIND_ONSHORE_DD_PMSG'] := 0.188889 ;
let subtech_share['YEAR_2020','NEW_WIND_ONSHORE_GB_PMSG'] := 0.147619 ;
let subtech_share['YEAR_2025','NEW_WIND_ONSHORE_DD_EESG'] := 0.042064 ;
let subtech_share['YEAR_2025','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.600794 ;
let subtech_share['YEAR_2025','NEW_WIND_ONSHORE_DD_PMSG'] := 0.197619 ;
let subtech_share['YEAR_2025','NEW_WIND_ONSHORE_GB_PMSG'] := 0.159524 ;
let subtech_share['YEAR_2030','NEW_WIND_ONSHORE_DD_EESG'] := 0.023810 ;
let subtech_share['YEAR_2030','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.598413 ;
let subtech_share['YEAR_2030','NEW_WIND_ONSHORE_DD_PMSG'] := 0.206349 ;
let subtech_share['YEAR_2030','NEW_WIND_ONSHORE_GB_PMSG'] := 0.171429 ;
let subtech_share['YEAR_2035','NEW_WIND_ONSHORE_DD_EESG'] := 0.019048 ;
let subtech_share['YEAR_2035','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.576191 ;
let subtech_share['YEAR_2035','NEW_WIND_ONSHORE_DD_PMSG'] := 0.220635 ;
let subtech_share['YEAR_2035','NEW_WIND_ONSHORE_GB_PMSG'] := 0.184127 ;
let subtech_share['YEAR_2040','NEW_WIND_ONSHORE_DD_EESG'] := 0.014286 ;
let subtech_share['YEAR_2040','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.553968 ;
let subtech_share['YEAR_2040','NEW_WIND_ONSHORE_DD_PMSG'] := 0.234921 ;
let subtech_share['YEAR_2040','NEW_WIND_ONSHORE_GB_PMSG'] := 0.196825 ;
let subtech_share['YEAR_2045','NEW_WIND_ONSHORE_DD_EESG'] := 0.007143 ;
let subtech_share['YEAR_2045','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.528484 ;
let subtech_share['YEAR_2045','NEW_WIND_ONSHORE_DD_PMSG'] := 0.249961 ;
let subtech_share['YEAR_2045','NEW_WIND_ONSHORE_GB_PMSG'] := 0.214413 ;
let subtech_share['YEAR_2050','NEW_WIND_ONSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2050','NEW_WIND_ONSHORE_GB_DFIG_SCIG'] := 0.503000 ;
let subtech_share['YEAR_2050','NEW_WIND_ONSHORE_DD_PMSG'] := 0.265000 ;
let subtech_share['YEAR_2050','NEW_WIND_ONSHORE_GB_PMSG'] := 0.232000 ;
let subtech_share['YEAR_2020','WIND_OFFSHORE_DD_EESG'] := 0.052558 ;
let subtech_share['YEAR_2020','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.197436 ;
let subtech_share['YEAR_2020','WIND_OFFSHORE_DD_PMSG'] := 0.568047 ;
let subtech_share['YEAR_2020','WIND_OFFSHORE_GB_PMSG'] := 0.181959 ;
let subtech_share['YEAR_2025','WIND_OFFSHORE_DD_EESG'] := 0.026279 ;
let subtech_share['YEAR_2025','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.245955 ;
let subtech_share['YEAR_2025','WIND_OFFSHORE_DD_PMSG'] := 0.586942 ;
let subtech_share['YEAR_2025','WIND_OFFSHORE_GB_PMSG'] := 0.140823 ;
let subtech_share['YEAR_2030','WIND_OFFSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2030','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.294475 ;
let subtech_share['YEAR_2030','WIND_OFFSHORE_DD_PMSG'] := 0.605836 ;
let subtech_share['YEAR_2030','WIND_OFFSHORE_GB_PMSG'] := 0.099688 ;
let subtech_share['YEAR_2035','WIND_OFFSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2035','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.296327 ;
let subtech_share['YEAR_2035','WIND_OFFSHORE_DD_PMSG'] := 0.600031 ;
let subtech_share['YEAR_2035','WIND_OFFSHORE_GB_PMSG'] := 0.103642 ;
let subtech_share['YEAR_2040','WIND_OFFSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2040','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.298180 ;
let subtech_share['YEAR_2040','WIND_OFFSHORE_DD_PMSG'] := 0.594225 ;
let subtech_share['YEAR_2040','WIND_OFFSHORE_GB_PMSG'] := 0.107596 ;
let subtech_share['YEAR_2045','WIND_OFFSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2045','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.299090 ;
let subtech_share['YEAR_2045','WIND_OFFSHORE_DD_PMSG'] := 0.592113 ;
let subtech_share['YEAR_2045','WIND_OFFSHORE_GB_PMSG'] := 0.108798 ;
let subtech_share['YEAR_2050','WIND_OFFSHORE_DD_EESG'] := 0.000000 ;
let subtech_share['YEAR_2050','WIND_OFFSHORE_GB_DFIG_SCIG'] := 0.300000 ;
let subtech_share['YEAR_2050','WIND_OFFSHORE_DD_PMSG'] := 0.590000 ;
let subtech_share['YEAR_2050','WIND_OFFSHORE_GB_PMSG'] := 0.110000 ;
let subtech_share['YEAR_2020','PV_ROOF_C_SI'] := 0.954000 ;
let subtech_share['YEAR_2020','PV_ROOF_CDTE'] := 0.024000 ;
let subtech_share['YEAR_2020','PV_ROOF_CIGS'] := 0.019000 ;
let subtech_share['YEAR_2020','PV_ROOF_A_SIGE'] := 0.003000 ;
let subtech_share['YEAR_2025','PV_ROOF_C_SI'] := 0.945000 ;
let subtech_share['YEAR_2025','PV_ROOF_CDTE'] := 0.027500 ;
let subtech_share['YEAR_2025','PV_ROOF_CIGS'] := 0.023334 ;
let subtech_share['YEAR_2025','PV_ROOF_A_SIGE'] := 0.004167 ;
let subtech_share['YEAR_2030','PV_ROOF_C_SI'] := 0.936000 ;
let subtech_share['YEAR_2030','PV_ROOF_CDTE'] := 0.031000 ;
let subtech_share['YEAR_2030','PV_ROOF_CIGS'] := 0.027667 ;
let subtech_share['YEAR_2030','PV_ROOF_A_SIGE'] := 0.005333 ;
let subtech_share['YEAR_2035','PV_ROOF_C_SI'] := 0.927000 ;
let subtech_share['YEAR_2035','PV_ROOF_CDTE'] := 0.034500 ;
let subtech_share['YEAR_2035','PV_ROOF_CIGS'] := 0.032000 ;
let subtech_share['YEAR_2035','PV_ROOF_A_SIGE'] := 0.006500 ;
let subtech_share['YEAR_2040','PV_ROOF_C_SI'] := 0.918000 ;
let subtech_share['YEAR_2040','PV_ROOF_CDTE'] := 0.038000 ;
let subtech_share['YEAR_2040','PV_ROOF_CIGS'] := 0.036333 ;
let subtech_share['YEAR_2040','PV_ROOF_A_SIGE'] := 0.007667 ;
let subtech_share['YEAR_2045','PV_ROOF_C_SI'] := 0.909000 ;
let subtech_share['YEAR_2045','PV_ROOF_CDTE'] := 0.041500 ;
let subtech_share['YEAR_2045','PV_ROOF_CIGS'] := 0.040666 ;
let subtech_share['YEAR_2045','PV_ROOF_A_SIGE'] := 0.008834 ;
let subtech_share['YEAR_2050','PV_ROOF_C_SI'] := 0.900000 ;
let subtech_share['YEAR_2050','PV_ROOF_CDTE'] := 0.045000 ;
let subtech_share['YEAR_2050','PV_ROOF_CIGS'] := 0.045000 ;
let subtech_share['YEAR_2050','PV_ROOF_A_SIGE'] := 0.010000 ;
let subtech_share['YEAR_2020','PV_GROUND_C_SI'] := 0.954000 ;
let subtech_share['YEAR_2020','PV_GROUND_CDTE'] := 0.024000 ;
let subtech_share['YEAR_2020','PV_GROUND_CIGS'] := 0.019000 ;
let subtech_share['YEAR_2020','PV_GROUND_A_SIGE'] := 0.003000 ;
let subtech_share['YEAR_2025','PV_GROUND_C_SI'] := 0.945000 ;
let subtech_share['YEAR_2025','PV_GROUND_CDTE'] := 0.027500 ;
let subtech_share['YEAR_2025','PV_GROUND_CIGS'] := 0.023334 ;
let subtech_share['YEAR_2025','PV_GROUND_A_SIGE'] := 0.004167 ;
let subtech_share['YEAR_2030','PV_GROUND_C_SI'] := 0.936000 ;
let subtech_share['YEAR_2030','PV_GROUND_CDTE'] := 0.031000 ;
let subtech_share['YEAR_2030','PV_GROUND_CIGS'] := 0.027667 ;
let subtech_share['YEAR_2030','PV_GROUND_A_SIGE'] := 0.005333 ;
let subtech_share['YEAR_2035','PV_GROUND_C_SI'] := 0.927000 ;
let subtech_share['YEAR_2035','PV_GROUND_CDTE'] := 0.034500 ;
let subtech_share['YEAR_2035','PV_GROUND_CIGS'] := 0.032000 ;
let subtech_share['YEAR_2035','PV_GROUND_A_SIGE'] := 0.006500 ;
let subtech_share['YEAR_2040','PV_GROUND_C_SI'] := 0.918000 ;
let subtech_share['YEAR_2040','PV_GROUND_CDTE'] := 0.038000 ;
let subtech_share['YEAR_2040','PV_GROUND_CIGS'] := 0.036333 ;
let subtech_share['YEAR_2040','PV_GROUND_A_SIGE'] := 0.007667 ;
let subtech_share['YEAR_2045','PV_GROUND_C_SI'] := 0.909000 ;
let subtech_share['YEAR_2045','PV_GROUND_CDTE'] := 0.041500 ;
let subtech_share['YEAR_2045','PV_GROUND_CIGS'] := 0.040666 ;
let subtech_share['YEAR_2045','PV_GROUND_A_SIGE'] := 0.008834 ;
let subtech_share['YEAR_2050','PV_GROUND_C_SI'] := 0.900000 ;
let subtech_share['YEAR_2050','PV_GROUND_CDTE'] := 0.045000 ;
let subtech_share['YEAR_2050','PV_GROUND_CIGS'] := 0.045000 ;
let subtech_share['YEAR_2050','PV_GROUND_A_SIGE'] := 0.010000 ;

# Known accepted approximation: the pre-2020 legacy stock (p="2015_2020") gets the YEAR_2020
# share applied via F_new_initialisation, since no earlier vintage breakdown exists.
# WIND_ONSHORE/NEW_WIND_ONSHORE/WIND_OFFSHORE/PV_ROOF/PV_GROUND no longer exist as technologies
# with their own F_new -- fix each sub-tech's share of the TOTAL new-build across its sibling
# sub-techs directly (TECHNOLOGIES_OF_ELECGEN_FAMILIES/MODELS_OF_... are pure grouping labels here).
# Using a +/-3% tolerance band rather than exact equality: a strict equality over-determines
# the system together with the legacy-vintage decommissioning schedule (distribution_init_general/
# phase_new_build/store_F_decom_up_to) for low-share sub-techs (e.g. PV_ROOF_CDTE), causing
# infeasibility even with correct share data. Confirmed via IIS that this is the actual cause,
# not a data bug (that separate bug -- commented-out YEAR_2020 lines -- was fixed above).
subject to elecgen_subtech_fixed_split_upper {p in PHASE union {"2015_2020"}, y_stop in PHASE_STOP[p],
                                          j in TECHNOLOGIES_OF_ELECGEN_FAMILIES,
                                          i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES[j]}:
    F_new[p, i] <= 1.01 * subtech_share[y_stop, i] * sum {k in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES[j]} F_new[p, k];
subject to elecgen_subtech_fixed_split_lower {p in PHASE union {"2015_2020"}, y_stop in PHASE_STOP[p],
                                          j in TECHNOLOGIES_OF_ELECGEN_FAMILIES,
                                          i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES[j]}:
    F_new[p, i] >= 0.99 * subtech_share[y_stop, i] * sum {k in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES[j]} F_new[p, k];
# --- END TEMPORARY market-share block ---
