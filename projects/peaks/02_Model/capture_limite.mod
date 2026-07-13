# ===========================================================================
# 1. DÉCLARATION DES PARAMÈTRES (Requis pour le .dat)
# ===========================================================================
param max_capture_totale;

# ===========================================================================
# 2. DÉCLARATION DU SET REGROUPANT TOUTES LES TECHNOLOGIES DE CAPTURE
# ===========================================================================
set MES_TECHS_CAPTURE := {
    # Technologies of CC
    'DAC_HT', 'DAC_LT', 'CARBON_CAPTURE', 'CARBON_CAPTURE_AMINES', 'CARBON_CAPTURE_MEMBRANES', 'CARBON_CAPTURE_MOF',

    # Technologies of CCS
    #'EOR', 'DOGR', 'UNMINEABLE_COAL_SEAM', 'DEEP_SALINE', 'MINES_STORAGE', 'CARBON_MINERALIZATION', 'CARBON_TRANSPORT_INJECTION',

    # Energy Technologies with CC
    'ATR_CCS', 'BIOGAS_ATR_CCS', 'SMR_CCS', 'BIOGAS_SMR_CCS', 'BIOMASS_GAS_EF_H2_CCS', 'BIOMASS_GAS_FB_H2_CCS',
    'COAL_GAS_H2_CCS', 'COAL_GAS_H2_ADV_CCS', 'CCGT_CC', 'CCGT_BIOGAS_CC', 'COAL_IGCC_CC', 'COAL_US_CC',
    'DHN_COGEN_WASTE_CC', 'H2_NG_CCGT_CCS', 'H2_SNG_CCGT_CCS', 'IND_BOILER_WASTE_CC', 'IND_COGEN_WASTE_CC'
};

# ===========================================================================
# 3. CONTRAINTE DE CAPTURE CUMULÉE AVEC ANNUAL_PROD
# ===========================================================================
# Cette contrainte va sommer automatiquement le 'Annual_Prod' de toutes
# les technologies listées dans le set ci-dessus.
subject to contrainte_max_capture:
    sum {t in MES_TECHS_CAPTURE} Annual_Prod['YEAR_2050', t] <= max_capture_totale;