# 1. On déclare un ensemble pour stocker tes nouvelles périodes de pointe
set PEAK_PERIODS;

# 2. On utilise l'instruction 'let' pour injecter tes pointes dans le set PERIODS global.
# Contrairement à ':=', l'opérateur 'union' avec 'let' est autorisé après le .dat.
let PERIODS := PERIODS union PEAK_PERIODS;