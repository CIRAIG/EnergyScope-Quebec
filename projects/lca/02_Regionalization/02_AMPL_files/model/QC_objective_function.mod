drop obj;
minimize obj2: sum{y in YEARS} (TotalCost[y] + 1e-9*(TotalABROAD[y,'m_CCS_all'] + TotalLCIA[y,'REQD'] + TotalLCIA[y,'RHHD']));