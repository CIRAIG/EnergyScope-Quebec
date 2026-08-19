minimize obj:     TotalTransitionCost + Recycling_shortfall_penalty_total;  # active for min-cost runs -- shortfall penalty kept out of TotalTransitionCost so reported cost stays real
minimize obj_co2: TotalGWPTransition;        # active for min-CO2 runs
