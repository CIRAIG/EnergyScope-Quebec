"""
run_pareto_sweep.py - Pareto sweep over two directions:

  (A) min-CO2  : objective = obj_co2 (TotalEmission),   sweep cost caps   [M$CAD]
  (B) min-cost : objective = obj     (TotalTransitionCost), sweep CO2 caps [ktCO2-eq.]

Run names:
  Pareto_minCO2_cost<N>k   — direction A
  Pareto_minCost_co2<N>kt  — direction B

After all runs, generates out/pareto_front.html.

Usage:
  python run_pareto_sweep.py
"""

import os, sys, time
from pathlib import Path

# ---------------------------------------------------------------------------
# !! CONFIGURE HERE !!
# ---------------------------------------------------------------------------

# (A) min-CO2 sweep: cost caps [M$CAD], high -> low
COST_LIMITS_MCAD = [
    1_200_000,
    1_250_000,
    1_350_000,
    #1_470_000,
    #1_500_000,
    1_750_000,
    #2_250_000,
    #3_000_000,
    #5_000_000,
]

# (B) min-cost sweep: CO2 budget caps [ktCO2-eq.], low -> high
# TotalEmission = sum of TotalGWP[y] over all years (kt CO2-eq./y, NOT multiplied by 5)
# Use the unconstrained min-CO2 result as the lower bound reference (~334 kt / 5y ~ 66.8 kt)
# and the unconstrained min-cost result as the upper bound.
CO2_LIMITS_KT = [
    #20_000,
    #30_000,
    #50_000,
    65_000,
    80_000,
    #85_000,
    #95_000,
    100_000,
    125_000,
    175_000,
    #200_000,
    250_000,
    #275_000,
    300_000,
    #500_000,#Useless after this value 
    800_000,#Useless after this value
]

# Rolling horizon settings (mirror run_main.py)
N_year_opti    = 30
N_year_overlap = 0

# Model variant
TYPE_OF_MODEL = 'MO'

# ---------------------------------------------------------------------------
# Paths (same logic as run_main.py)
# ---------------------------------------------------------------------------
curr_dir         = Path(os.path.dirname(os.path.abspath(__file__)))
pth_proj         = curr_dir.parent
pth_repo         = pth_proj.parent.parent

pth_model        = str(pth_proj / 'model')
pth_data         = str(pth_repo / 'shared' / 'data')
pth_shared_model = str(pth_repo / 'shared' / 'model')
pth_output_all   = str(pth_proj / 'out')

pymodPath = str(pth_proj / 'pylib')
sys.path.insert(0, pymodPath)

from ampl_object       import AmplObject
from ampl_preprocessor import AmplPreProcessor
from ampl_collector    import AmplCollector

# ---------------------------------------------------------------------------
# File lists (MO only — mirrors run_main.py)
# ---------------------------------------------------------------------------
mod_1_path = [
    os.path.join(pth_shared_model, 'QC_es_main.mod'),
    os.path.join(pth_model,        'QC_es_pathway.mod'),
    os.path.join(pth_model,        'QC_es_obj_pathway.mod'),
    os.path.join(pth_model,        'PES_store_variables.mod'),
]
mod_2_path = [
    os.path.join(pth_model, 'EXTRA_INFOS.dat'),
    os.path.join(pth_data,  'QC_data.dat'),
    os.path.join(pth_model, 'PES_scenarios.mod'),
    os.path.join(pth_data,  'EUD/out_eud.dat'),
    os.path.join(pth_data,  'Techs/out_techs.dat'),
    os.path.join(pth_data,  'Shares/out_shares.dat'),
    os.path.join(pth_model, 'QC_data_pathway.dat'),
    os.path.join(pth_model, 'PES_data_decom_allowed_2020.dat'),
    os.path.join(pth_model, 'fix.mod'),
]
dat_path = [
    os.path.join(pth_model, 'PES_seq_opti.dat'),
    os.path.join(pth_model, 'PES_data_set_AGE_2020.dat'),
]
dat_path_0 = dat_path + [os.path.join(pth_model, 'PES_data_remaining.dat')]
dat_path   = dat_path + [os.path.join(pth_model, 'PES_data_remaining_wnd.dat')]

# ---------------------------------------------------------------------------
# Gurobi / AMPL options
# ---------------------------------------------------------------------------
gurobi_options_str = ' '.join([
    'predual=-1', 'method=2', 'crossover=0', 'threads=0',
    'prepasses=3', 'barconvtol=1e-6', 'presolve=-1',
    'iisfind=1', 'outlev=1',
])
ampl_options = {
    'show_stats':      1,
    'log_file':        os.path.join(pth_proj, 'log.txt'),
    'presolve':        0,
    'presolve_eps':    1e-6,
    'presolve_fixeps': 1e-6,
    'show_boundtol':   0,
    'gurobi_options':  gurobi_options_str,
    '_log_input_only': False,
}


# ---------------------------------------------------------------------------
# Single-run helper
# ---------------------------------------------------------------------------

def run_one(case_study, expl_text, objective,
            cost_limit_mcad=2_000_000, co2_limit_kt=None):
    """
    Run the full rolling-horizon optimisation for one configuration.

    Parameters
    ----------
    objective       : 'min_co2'   -> drop obj, obj_weighted;  restore obj_co2
                      'min_cost'  -> drop obj_co2, obj_weighted; restore obj
                      'weighted'  -> drop obj, obj_co2; restore obj_weighted; set alpha
    cost_limit_mcad : max_cost_budget [M$CAD]
    co2_limit_kt    : max_co2_budget  [ktCO2-eq.], None = Infinity
    """
    print(f'\n{"="*70}')
    print(f'  RUNNING : {case_study}')
    print(f'  Objective : {objective}')
    print(f'  Cost cap  : {cost_limit_mcad:,} M$CAD')
    print(f'  CO2 cap   : {co2_limit_kt if co2_limit_kt else "Infinity"} ktCO2-eq.')
    print(f'{"="*70}\n')

    output_folder = os.path.join(pth_output_all, case_study)
    output_file   = os.path.join(output_folder, '_Results.pkl')

    if os.path.exists(output_file):
        print(f'  [SKIP] {case_study} — pkl already exists.')
        return True

    open(os.path.join(pth_model, 'fix.mod'), 'w').close()

    ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                        type_model=TYPE_OF_MODEL, working_dir=pth_model)
    ampl_0.clean_history()
    ampl_pre       = AmplPreProcessor(ampl_0, N_year_opti, N_year_overlap)
    ampl_collector = AmplCollector(ampl_pre, output_file, expl_text)

    t = time.time()

    for i in range(len(ampl_pre.years_opti)):
        t_i = time.time()

        curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
        ampl_pre.remaining_update(i)

        ampl = AmplObject(mod_1_path, mod_2_path, dat_path, ampl_options,
                          type_model=TYPE_OF_MODEL, working_dir=pth_model)
        ampl.ampl.eval("shell 'gurobi -v';")

        # Switch objective — drop the unused one so only one is active
        if objective == 'min_co2':
            ampl.ampl.eval('drop obj;')
        else:  # min_cost
            ampl.ampl.eval('drop obj_co2;')

        # Set bounds
        ampl.set_params('max_cost_budget', float(cost_limit_mcad))
        if co2_limit_kt is not None:
            ampl.set_params('max_co2_budget', float(co2_limit_kt))

        solve_result, _ = ampl.run_ampl()
        sys.stdout.flush()

        if solve_result in ('infeasible', 'limit', 'failure'):
            print(f'\n=== INFEASIBLE at window {i+1} - skipping {case_study} ===')
            return False

        ampl.get_total_cost()
        ampl.get_cost_breakdown()
        ampl.get_cost_return()
        ampl.get_total_gwp()
        ampl.get_gwp_transition()
        ampl.get_resources()
        ampl.get_assets()
        ampl.get_annual_monthly_prod()
        ampl.get_new_old_decom()
        ampl.get_F_decom()
        ampl.get_number_of_units()
        ampl.get_year_balance()
        ampl.get_sto_levels()

        if i == 0:
            ampl_collector.init_storage(ampl)
        else:
            curr_years_wnd.remove(ampl_pre.year_to_rm)
        ampl_collector.update_storage(ampl, curr_years_wnd, i)
        ampl.set_init_sol()

        print(f'Window {i+1} done in {time.time()-t_i:.1f}s')

        if i == len(ampl_pre.years_opti) - 1:
            print(f'Total time: {time.time()-t:.1f}s')
            ampl_collector.clean_collector()
            ampl_collector.pkl()

    return True


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    completed, skipped = [], []

    # --- Direction A: min CO2, sweep cost caps ---
    for cost_limit in COST_LIMITS_MCAD:
        case_study = f'Pareto_minCO2_cost{cost_limit // 1000}k'
        expl_text  = (
            f'Pareto - min CO2 - cost cap {cost_limit} M$CAD'
            f' ({cost_limit // 1000} B$CAD) - perfect foresight'
            f' - initial distribution progressively decommissioned'
        )
        ok = run_one(case_study, expl_text,
                     objective='min_co2',
                     cost_limit_mcad=cost_limit)
        (completed if ok else skipped).append(case_study)

    # --- Direction B: min cost, sweep CO2 caps ---
    for co2_limit in CO2_LIMITS_KT:
        case_study = f'Pareto_minCost_co2{co2_limit // 1000}kt'
        expl_text  = (
            f'Pareto - min cost - CO2 cap {co2_limit} ktCO2-eq.'
            f' ({co2_limit // 1000} Mt) - perfect foresight'
            f' - initial distribution progressively decommissioned'
        )
        ok = run_one(case_study, expl_text,
                     objective='min_cost',
                     co2_limit_kt=co2_limit)
        (completed if ok else skipped).append(case_study)

    # Summary
    print('\n' + '='*70)
    print(f'Sweep complete: {len(completed)} succeeded, {len(skipped)} skipped.')
    if skipped:
        print('  Skipped (infeasible):', ', '.join(skipped))

    # Generate Pareto plot
    print('\nGenerating Pareto front plot...')
    try:
        if str(curr_dir) not in sys.path:
            sys.path.insert(0, str(curr_dir))
        import importlib
        import plot_pareto
        importlib.reload(plot_pareto)
        plot_pareto.plot_pareto(
            os.path.join(pth_output_all, '_Recap.csv'),
            pth_output_all,
        )
    except Exception as e:
        print(f'[WARNING] Could not generate Pareto plot: {e}')
        print('  Run `python plot_pareto.py` manually.')
