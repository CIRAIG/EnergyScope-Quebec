import pytest
from shared.models import energyscope_original_snapshot_2021, energyscope_original_snapshot_2023
from shared.utils import load_snapshot, run_model

def test_reference_years():

    ### 2021 ###
    results_original_snapshot_2021 = run_model(energyscope_original_snapshot_2021)
    new_model_2021 = load_snapshot(2021)
    results_new_snapshot_2021 = run_model(new_model_2021)

    tc_original_model_2021 = float(results_original_snapshot_2021.variables['TotalCost']['TotalCost'])
    tc_new_model_2021 = float(results_new_snapshot_2021.variables['TotalCost']['TotalCost'])

    assert tc_original_model_2021 == tc_new_model_2021

    ### 2023 ###
    results_original_snapshot_2023 = run_model(energyscope_original_snapshot_2023)
    new_model_2023 = load_snapshot(2023)
    results_new_snapshot_2023 = run_model(new_model_2023)

    tc_original_model_2023 = float(results_original_snapshot_2023.variables['TotalCost']['TotalCost'])
    tc_new_model_2023 = float(results_new_snapshot_2023.variables['TotalCost']['TotalCost'])

    assert tc_original_model_2023 == tc_new_model_2023