import pytest
import pandas as pd
from shared.models import energyscope_original_snapshot_2021, energyscope_original_snapshot_2023
from shared.utils import load_snapshot, run_model

_TOTALCOST_TOL = 0.0001  # MCAD/y — differences below this are solver numerical noise


def _fmult_diff_table(orig_result, new_result, n: int = 30) -> str:
    df_o = orig_result.variables['F_Mult'].copy()
    df_n = new_result.variables['F_Mult'].copy()

    for df in (df_o, df_n):
        if 'Run' in df.columns:
            df.drop(columns='Run', inplace=True)

    def _normalize_index(df):
        # Always use only the technology name (last index level) as the row key
        if isinstance(df.index, pd.MultiIndex):
            df = df.copy()
            df.index = df.index.get_level_values(-1)
        return df

    df_o = _normalize_index(df_o)[['F_Mult']].rename(columns={'F_Mult': 'original'})
    df_n = _normalize_index(df_n)[['F_Mult']].rename(columns={'F_Mult': 'new'})

    merged = df_o.join(df_n, how='outer').fillna(0)
    merged['diff'] = merged['new'] - merged['original']

    top = merged.reindex(merged['diff'].abs().nlargest(n).index)

    return top.to_string(float_format=lambda x: f"{x:,.10f}")


def test_reference_years():

    ### 2021 ###
    results_original_snapshot_2021 = run_model(energyscope_original_snapshot_2021)
    new_model_2021 = load_snapshot(2021)
    results_new_snapshot_2021 = run_model(new_model_2021)

    tc_original_model_2021 = float(results_original_snapshot_2021.variables['TotalCost']['TotalCost'].iloc[0])
    tc_new_model_2021 = float(results_new_snapshot_2021.variables['TotalCost']['TotalCost'].iloc[0])

    if abs(tc_new_model_2021 - tc_original_model_2021) > _TOTALCOST_TOL:
        table = _fmult_diff_table(results_original_snapshot_2021, results_new_snapshot_2021)
        diff = tc_new_model_2021 - tc_original_model_2021
        pytest.fail(
            f"\n[2021] TotalCost mismatch:"
            f"\n  original : {tc_original_model_2021:.6f}"
            f"\n  new      : {tc_new_model_2021:.6f}"
            f"\n  diff     : {diff:+.6f}"
            f"\n\nTop 30 F_Mult differences (original | new | diff):\n{table}"
        )

    ### 2023 ###
    results_original_snapshot_2023 = run_model(energyscope_original_snapshot_2023)
    new_model_2023 = load_snapshot(2023)
    results_new_snapshot_2023 = run_model(new_model_2023)

    tc_original_model_2023 = float(results_original_snapshot_2023.variables['TotalCost']['TotalCost'].iloc[0])
    tc_new_model_2023 = float(results_new_snapshot_2023.variables['TotalCost']['TotalCost'].iloc[0])

    if abs(tc_new_model_2023 - tc_original_model_2023) > _TOTALCOST_TOL:
        table = _fmult_diff_table(results_original_snapshot_2023, results_new_snapshot_2023)
        diff = tc_new_model_2023 - tc_original_model_2023
        pytest.fail(
            f"\n[2023] TotalCost mismatch:"
            f"\n  original : {tc_original_model_2023:.6f}"
            f"\n  new      : {tc_new_model_2023:.6f}"
            f"\n  diff     : {diff:+.6f}"
            f"\n\nTop 30 F_Mult differences (original | new | diff):\n{table}"
        )
