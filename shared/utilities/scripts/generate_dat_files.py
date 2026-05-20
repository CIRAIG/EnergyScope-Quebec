"""
generate_dat_files.py
Generates per-year QC_techs_<year>.dat, QC_eud_<year>.dat, and
QC_shares_<year>.dat files from snapshot model results and prospective ratio CSVs.

Extracted from Prospective_parameters/02_Write_dat_files_for_all_years.ipynb.
Entry point: run()
"""

import re
import pandas as pd
from pathlib import Path

from energyscope.models import Model
from energyscope.energyscope import Energyscope
from energyscope.result import postprocessing

_ZERO_THR  = 8e-6
YEARS_2020 = [2020]
YEARS_2023 = [2025, 2030, 2035, 2040, 2045, 2050]
default_values = {  # default values, thus we do not need to write them
    'f_min': 0.0,
    'f_max': 10000,
    'out_max': 'Infinity',
    'fmax_perc_mob': 1.0,
    'fmin_perc_mob': 0.0,
    'fmax_perc': 1.0,
    'fmin_perc': 0.0,
    'avail': 0.0,
}


def _fmt(val):
    """Format a float for AMPL output, converting Python inf to Infinity."""
    import math
    return 'Infinity' if math.isinf(float(val)) else str(val)


# ── Snapshot helpers ──────────────────────────────────────────────────────────

def _build_snapshot_model(snapshot_dir: Path, validation_dat: str | None = None) -> Model:
    """Assemble a snapshot Model from the given directory and optional validation dat file.

    Args:
        snapshot_dir:   path to the snapshot model directory (e.g. ES_Snapshot/)
        validation_dat: filename of the validation dat file within snapshot_dir,
                        or None to run without any validation constraints (free run)
    """
    files = [
        ('mod', snapshot_dir / 'QC_es_main.mod'),
        ('mod', snapshot_dir / 'QC_objective_function.mod'),
        ('dat', snapshot_dir / 'QC_data.dat'),
        ('dat', snapshot_dir / 'QC_mob_techs_dist_B2D.dat'),
        ('dat', snapshot_dir / 'QC_techs_B2D.dat'),
        ('dat', snapshot_dir / 'QC_mob_params.dat'),
    ]
    if validation_dat is not None:
        files.append(('dat', snapshot_dir / validation_dat))
    return Model(files)


def _run_snapshot(model: Model):
    """Solve the snapshot model and return post-processed results."""
    es = Energyscope(model=model, solver_options={'solver': 'gurobi', 'solver_msg': 0})
    return postprocessing(es.calc())


def _build_params_df(res) -> pd.DataFrame:
    """Extract techno-economic parameters from snapshot results into a flat DataFrame.

    Does NOT include capacity/availability bounds (f_min, f_max, avail, out_max) —
    those are handled separately by _build_bounds_df.

    Args:
        res: post-processed snapshot results object (from postprocessing())
    """
    df_list = []
    for param in ['layers_in_out', 'c_inv', 'c_maint', 'c_op', 'c_p', 'c_p_t',
                  'lifetime', 'ref_size', 'trl',
                  'loss_coeff',
                  'storage_eff_in', 'storage_eff_out']:
        df = res.parameters[param].reset_index()
        df = df[df[param] != 0]
        df['param'] = param
        df = df.rename(columns={param: 'Value', 'index': 'index0'})
        df = df.drop(columns=['Run'])
        if 'index1' not in df.columns:
            df['index1'] = None
        df_list.append(df)
    return (pd.concat(df_list, ignore_index=True)
              .sort_values(by=['index0', 'index1'])
              .reset_index(drop=True))


def _build_bounds_df(res) -> pd.DataFrame:
    """Extract capacity/availability bounds from snapshot results into a flat DataFrame.

    Extracts f_min, f_max, avail, out_max — parameters whose correct source
    depends on the year (validation runs for 2020/2025, free run for 2030-2050).

    Args:
        res: post-processed snapshot results object (from postprocessing())
    """
    df_list = []
    for param in ['f_min', 'f_max', 'avail', 'out_max']:
        df = res.parameters[param].reset_index()
        df = df[df[param] != 0]
        df['param'] = param
        df = df.rename(columns={param: 'Value', 'index': 'index0'})
        df = df.drop(columns=['Run'])
        if 'index1' not in df.columns:
            df['index1'] = None
        df_list.append(df)
    return (pd.concat(df_list, ignore_index=True)
              .sort_values(by=['index0', 'index1'])
              .reset_index(drop=True))


def _load_transition_mob_maps(transition_dat_file: Path) -> dict:
    """Read MODELS_OF_TECHNOLOGIES_OF_*_ALL_DISTANCES sets from QC_data.dat."""
    pat = re.compile(
        r'set MODELS_OF_TECHNOLOGIES_OF_\w+_ALL_DISTANCES\s*\["(\w+)"\]\s*:=(.*?);',
        re.DOTALL,
    )
    with open(transition_dat_file, encoding='utf-8', errors='replace') as f:
        lines = [l for l in f if not l.lstrip().startswith('#')]
    content = ''.join(lines)
    mob_maps = {}
    for m in pat.finditer(content):
        base     = m.group(1)
        variants = re.findall(r'\b([A-Z][A-Z0-9_]+)\b', m.group(2))
        mob_maps[base] = variants
    return mob_maps


# ── EUD writers ───────────────────────────────────────────────────────────────

def _write_demand_file_2020(eud_2021, projected_demands, output_dir: Path,
                             scenario: str) -> None:
    """Write QC_eud_2020.dat using 2021 snapshot values directly (no ratio scaling).

    Args:
        eud_2021:          end_uses_demand_year DataFrame from the 2021 snapshot
        projected_demands: prospective demand ratios DataFrame (unused for 2020, kept for signature consistency)
        output_dir:        directory where QC_eud_2020.dat will be written
        scenario:          demand scenario name (e.g. 'Current Measure')
    """
    year = 2020
    df = eud_2021.reset_index().sort_values(by=['index1', 'index0'])
    with open(output_dir / f'QC_eud_{year}.dat', 'w', encoding='utf8') as f:
        for sector in df['index1'].unique():
            f.write(f"\n# {sector}\n")
            df_sector = df[df['index1'] == sector]
            for eud_type in df_sector['index0'].unique():
                value = df_sector[df_sector['index0'] == eud_type]['end_uses_demand_year'].values[0]
                if abs(value) < _ZERO_THR:
                    continue
                f.write(f"let end_uses_demand_year['YEAR_{year}','{eud_type}','{sector}'] := {value} ; \n")


def _write_demand_file_from_2023(year: int, eud_2023, projected_demands,
                                  output_dir: Path, scenario: str) -> None:
    """Write QC_eud_<year>.dat by scaling 2023 snapshot EUD with prospective demand ratios.

    Args:
        year:              target year (2025–2050)
        eud_2023:          end_uses_demand_year DataFrame from the 2023 snapshot
        projected_demands: prospective demand ratios DataFrame (Year, Scenario, EUD, Sector, Ratio 2020)
        output_dir:        directory where QC_eud_<year>.dat will be written
        scenario:          demand scenario name (e.g. 'Current Measure')
    """
    def _eud_with_ratio(yr):
        merged = pd.merge(
            eud_2023.reset_index()[['index0', 'index1', 'end_uses_demand_year']],
            projected_demands[
                (projected_demands.Year == yr) & (projected_demands.Scenario == scenario)
            ][['EUD', 'Sector', 'Ratio 2020']],
            left_on=['index0', 'index1'], right_on=['EUD', 'Sector'], how='left',
        ).drop(columns=['EUD', 'Sector'], errors='ignore')
        merged['Ratio 2020'] = merged['Ratio 2020'].fillna(1.0)
        return merged.rename(columns={'Ratio 2020': f'ratio_{yr}'})

    df      = _eud_with_ratio(year)
    df_base = _eud_with_ratio(2025)[['index0', 'index1', 'ratio_2025']].rename(
        columns={'ratio_2025': 'ratio_base'})
    df = df.merge(df_base, on=['index0', 'index1'], how='left')
    df['ratio_base'] = df['ratio_base'].fillna(1.0)
    df = df.sort_values(by=['index1', 'index0'])

    with open(output_dir / f'QC_eud_{year}.dat', 'w', encoding='utf8') as f:
        for sector in df['index1'].unique():
            f.write(f"\n# {sector}\n")
            df_sector = df[df['index1'] == sector]
            for eud_type in df_sector['index0'].unique():
                row           = df_sector[df_sector['index0'] == eud_type].iloc[0]
                adjusted_ratio = row[f'ratio_{year}'] / row['ratio_base']
                if abs(row['end_uses_demand_year'] * adjusted_ratio) < _ZERO_THR:
                    continue
                f.write(
                    f"let end_uses_demand_year['YEAR_{year}','{eud_type}','{sector}']"
                    f" := {row['end_uses_demand_year']}*{adjusted_ratio} ; \n"
                )


# ── Tech writer ───────────────────────────────────────────────────────────────

def _write_techs_file(year: int, df_filtered, prospective_param_ca,
                       prospective_param_estd, prospective_lyrios,
                       mobility_sub_models: list, transition_mob_maps: dict,
                       output_dir: Path, df_bounds: pd.DataFrame = None,
                       normalize_to_2025: bool = False) -> None:
    """Write QC_techs_<year>.dat by applying prospective cost/efficiency ratios to snapshot values.

    Args:
        year:               target year (e.g. 2030)
        df_filtered:        flat DataFrame of snapshot techno-economic parameters
        prospective_param_ca/estd: prospective cost ratio DataFrames (CA source, ESTD fallback)
        prospective_lyrios: prospective layers_in_out ratio DataFrame
        mobility_sub_models: list of distance-variant tech names (no c_inv/c_maint written)
        transition_mob_maps: {base_tech: [variant_techs]} for lifetime propagation
        output_dir:         directory to write the .dat file into
        df_bounds:          flat DataFrame of f_min, f_max, avail, out_max (from _build_bounds_df)
        normalize_to_2025:  if True, ratios are expressed relative to 2025 rather than 2020
    """
    col_year = f'Ratio {year}/2020'
    col_base = 'Ratio 2025/2020'

    def _lookup(df, tech, secondary, is_flow):
        mask = (
            (df['ES_name_ES_QC'] == tech) & (df['Flow'] == secondary)
            if is_flow else
            (df['ES_name_ES_QC'] == tech) & (df['param'] == secondary)
        )
        rows = df[mask]
        if len(rows) > 1:
            raise ValueError(f'Multiple ratios for {tech}-{secondary}')
        return rows

    def get_ratio(primary_df, tech, secondary, is_flow=False, fallback_df=None):
        rows = _lookup(primary_df, tech, secondary, is_flow)
        if len(rows) == 0 and fallback_df is not None:
            rows = _lookup(fallback_df, tech, secondary, is_flow)
        if len(rows) == 0:
            return 1.0
        ratio_year = rows[col_year].values[0]
        if normalize_to_2025:
            return ratio_year / rows[col_base].values[0]
        return ratio_year

    with open(output_dir / f'QC_techs_{year}.dat', 'w', encoding='utf8') as f:

        for tech in df_filtered.index0.unique():
            df_tech = df_filtered[df_filtered['index0'] == tech].reset_index(drop=True)

            for i in range(len(df_tech)):
                param, tech, value = df_tech[['param', 'index0', 'Value']].iloc[i]

                if param in ['c_p', 'c_p_t', 'lifetime', 'ref_size', 'trl']:
                    if tech in mobility_sub_models:
                        continue
                    if param != 'c_p_t':
                        if abs(value) < _ZERO_THR:
                            continue
                        f.write(f"let {param}['YEAR_{year}','{tech}'] := {_fmt(value)} ; \n")
                    else:
                        period = df_tech['index1'].iloc[i]
                        if value != 1:
                            if abs(value) < _ZERO_THR:
                                continue
                            f.write(f"let {param}['YEAR_{year}','{tech}',{period}] := {_fmt(value)} ; \n")

                elif param == 'layers_in_out':
                    flow = df_tech['index1'].iloc[i]
                    if flow == tech:
                        if abs(value) < _ZERO_THR:
                            continue
                        f.write(f"let {param}['YEAR_{year}','{tech}','{flow}'] := {_fmt(value)} ; \n")
                        continue

                    if flow.startswith('ELECTRICITY'):
                        estd_flow = 'ELECTRICITY'
                    elif flow.startswith('NG') or flow.startswith('SNG'):
                        estd_flow = 'GAS'
                    elif flow.startswith('H2'):
                        estd_flow = 'H2'
                    elif flow == 'BIO_DIESEL':
                        estd_flow = 'DIESEL'
                    elif flow in ['CO2_E', 'CO2_A', 'CO2_C', 'CO2_CS']:
                        if 'BIODIESEL' in tech or 'DIESEL' in tech or 'HY_DIESEL' in tech:
                            estd_flow = 'DIESEL'
                        elif 'GASOLINE' in tech:
                            estd_flow = 'GASOLINE'
                        elif 'CNG' in tech or 'CSNG' in tech:
                            estd_flow = 'GAS'
                        elif 'PROPANE' in tech:
                            estd_flow = 'PROPANE'
                        elif 'HEV' in tech:
                            estd_flow = 'GASOLINE'
                        elif 'MEOH' in tech or 'PHEV' in tech:
                            estd_flow = 'GASOLINE'
                        elif 'COAL' in tech:
                            estd_flow = 'COAL'
                        elif 'WOOD' in tech or 'PYROLYSIS' == tech:
                            estd_flow = 'WOOD'
                        elif 'GAS' in tech:
                            estd_flow = 'GAS'
                        elif 'OIL' in tech:
                            estd_flow = 'LFO'
                        elif 'WASTE' in tech:
                            estd_flow = 'WASTE'
                        else:
                            estd_flow = flow
                    else:
                        estd_flow = flow

                    prospective_ratio = get_ratio(prospective_lyrios, tech, estd_flow, is_flow=True)
                    if abs(value * prospective_ratio) < _ZERO_THR:
                        continue
                    f.write(f"let {param}['YEAR_{year}','{tech}','{flow}'] := {_fmt(value * prospective_ratio)} ; \n")

                elif param in ['c_inv', 'c_maint', 'c_op']:
                    if tech in mobility_sub_models:
                        continue
                    prospective_ratio = get_ratio(
                        prospective_param_ca, tech, param, fallback_df=prospective_param_estd)
                    if abs(value * prospective_ratio) < _ZERO_THR:
                        continue
                    if param == 'c_op':
                        f.write(f"let {param}['YEAR_{year}','{tech}',{df_tech['index1'].iloc[i]}] := {_fmt(value * prospective_ratio)} ; \n")
                    else:
                        f.write(f"let {param}['YEAR_{year}','{tech}'] := {_fmt(value * prospective_ratio)} ; \n")

                elif param in ['loss_coeff']:
                    if abs(value) < _ZERO_THR:
                        continue
                    f.write(f"let {param}['YEAR_{year}','{tech}'] := {_fmt(value)} ; \n")

                elif param in ['storage_eff_in', 'storage_eff_out']:
                    layer = df_tech['index1'].iloc[i]
                    if abs(value) < _ZERO_THR:
                        continue
                    f.write(f"let {param}['YEAR_{year}','{tech}','{layer}'] := {_fmt(value)} ; \n")

                else:
                    raise ValueError(f'Unknown parameter {param}')

            f.write('\n')

        # Lifetime for mobility sub-models: inherited from base tech
        for base, subs in transition_mob_maps.items():
            base_lt = df_filtered[
                (df_filtered['index0'] == base) & (df_filtered['param'] == 'lifetime')
            ]['Value']
            if len(base_lt) == 0:
                continue
            for sub in subs:
                f.write(f"let lifetime['YEAR_{year}','{sub}'] := {base_lt.values[0]} ; \n")

        # Capacity / availability bounds (f_min, f_max, avail, out_max)
        if df_bounds is not None and not df_bounds.empty:
            f.write('\n# --- bounds ---\n')
            for _, row in df_bounds.iterrows():
                tech  = row['index0']
                param = row['param']
                value = row['Value']
                if abs(value) < _ZERO_THR or ((_fmt(value) if param == 'out_max' else value) == default_values[param]):
                    continue
                f.write(f"let {param}['YEAR_{year}','{tech}'] := {_fmt(value)} ; \n")


# ── Share-parameter helpers ───────────────────────────────────────────────────

# All scalar share parameters that are year-indexed in the transition model
# but appear as 0-dimensional parameters in the snapshot model.
_SCALAR_SHARE_PARAMS = [
    'share_mobility_public_min_sd', 'share_mobility_public_max_sd',
    'share_mobility_public_min_md', 'share_mobility_public_max_md',
    'share_mobility_public_min_ld', 'share_mobility_public_max_ld',
    'share_mobility_public_min_eld', 'share_mobility_public_max_eld',
    'share_public_rail_min_sd',  'share_public_rail_max_sd',
    'share_public_rail_min_md',  'share_public_rail_max_md',
    'share_public_rail_min_ld',  'share_public_rail_max_ld',
    'share_public_rail_min_eld', 'share_public_rail_max_eld',
    'share_public_air_min_ld',   'share_public_air_max_ld',
    'share_public_air_min_eld',  'share_public_air_max_eld',
    'share_freight_rail_min_ld',  'share_freight_rail_max_ld',
    'share_freight_rail_min_eld', 'share_freight_rail_max_eld',
    'share_freight_air_min_eld',  'share_freight_air_max_eld',
    'share_freight_maritime_min_eld', 'share_freight_maritime_max_eld',
    'share_freight_maritime_bulk_carrier',
    'share_freight_maritime_container',
    'share_freight_maritime_oil_tanker',
    'share_public_schoolbus_min_sd', 'share_public_schoolbus_max_sd',
    'share_heat_dhn_min', 'share_heat_dhn_max',
]


def _build_shares_df(res) -> dict:
    """Extract share parameters from a solved snapshot result.

    Follows the same pattern as _build_bounds_df: reads directly from the
    solved AMPL model so that the values reflect whatever the validation dat
    file (or QC_mob_params.dat) set them to.

    Returns a dict with keys:
        'scalar'       — {param_name: float}  year-scalar share_* params
        'fmin_perc_mob'— {tech: float}         mobility tech min distribution
        'fmax_perc_mob'— {tech: float}         mobility tech max distribution
        'fmin_perc'    — {tech: float}         heating tech min distribution
        'fmax_perc'    — {tech: float}         heating tech max distribution
    """
    result = {
        'scalar': {},
        'fmin_perc_mob': {},
        'fmax_perc_mob': {},
        'fmin_perc': {},
        'fmax_perc': {},
    }

    # 1-D indexed params — same extraction pattern as _build_bounds_df
    for key in ['fmin_perc_mob', 'fmax_perc_mob', 'fmin_perc', 'fmax_perc']:
        try:
            df = res.parameters[key].reset_index()
            df = df[df[key] != 0]
            df = df.drop(columns=['Run'], errors='ignore')
            df = df.rename(columns={'index': 'tech'})
            if 'tech' in df.columns:
                result[key] = dict(zip(df['tech'], df[key]))
        except Exception:
            pass

    # Scalar (0-D) share params — no meaningful index after reset_index()
    for name in _SCALAR_SHARE_PARAMS:
        try:
            df = res.parameters[name].reset_index()
            df = df.drop(columns=['Run'], errors='ignore')
            # Only column left is the value column named after the param
            val = float(df[name].iloc[0])
            result['scalar'][name] = val
        except Exception:
            pass

    return result


def _write_shares_file(year: int, shares: dict, output_dir: Path) -> None:
    """Write QC_shares_<year>.dat with mobility and heating share parameters.

    Parameters written (all year-indexed for the transition model):
        - share_*           modal splits, boat shares, DHN heat share (scalar params)
        - fmin_perc_mob     mobility tech distribution min
        - fmax_perc_mob     mobility tech distribution max
        - fmin_perc         heating tech distribution min
        - fmax_perc         heating tech distribution max

    Args:
        year:       target year (e.g. 2020)
        shares:     dict returned by _build_shares_df()
        output_dir: directory to write QC_shares_<year>.dat into
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    yr_tag = f'YEAR_{year}'

    with open(output_dir / f'QC_shares_{year}.dat', 'w', encoding='utf-8') as f:

        if shares['scalar']:
            f.write(f'# Modal share parameters — {yr_tag}\n')
            for name, val in shares['scalar'].items():
                f.write(f"let {name}['{yr_tag}'] := {_fmt(val)} ;\n")

        if shares['fmin_perc_mob']:
            f.write('\n# Mobility technology distribution — minimum shares\n')
            for tech, val in shares['fmin_perc_mob'].items():
                if abs(val) >= _ZERO_THR and val != default_values['fmin_perc_mob']:
                    f.write(f"let fmin_perc_mob['{yr_tag}','{tech}'] := {_fmt(val)} ;\n")

        if shares['fmax_perc_mob']:
            f.write('\n# Mobility technology distribution — maximum shares\n')
            for tech, val in shares['fmax_perc_mob'].items():
                if val != default_values['fmax_perc_mob']:
                    f.write(f"let fmax_perc_mob['{yr_tag}','{tech}'] := {_fmt(val)} ;\n")

        if shares['fmin_perc']:
            f.write('\n# Heating technology distribution — minimum shares\n')
            for tech, val in shares['fmin_perc'].items():
                if abs(val) >= _ZERO_THR and val != default_values['fmin_perc']:
                    f.write(f"let fmin_perc['{yr_tag}','{tech}'] := {_fmt(val)} ;\n")

        if shares['fmax_perc']:
            f.write('\n# Heating technology distribution — maximum shares\n')
            for tech, val in shares['fmax_perc'].items():
                if val != default_values['fmax_perc']:
                    f.write(f"let fmax_perc['{yr_tag}','{tech}'] := {_fmt(val)} ;\n")


# ── Public entry point ────────────────────────────────────────────────────────

def run(snapshot_dir: Path, prospective_dir: Path,
        output_techs_dir: Path, output_eud_dir: Path,
        output_shares_dir: Path, scenario: str,
        validation_2021: str = 'QC_validation_2021.dat',
        validation_2023: str = 'QC_validation_2023.dat') -> None:
    """Generate all per-year QC_techs_<year>.dat, QC_eud_<year>.dat, and QC_shares_<year>.dat files.

    Args:
        snapshot_dir:       path to the snapshot model directory (ES_Snapshot/)
        prospective_dir:    path to Prospective_parameters/ (contains Data/ and Outputs/)
        output_techs_dir:   where to write QC_techs_<year>.dat files
        output_eud_dir:     where to write QC_eud_<year>.dat files
        output_shares_dir:  where to write QC_shares_<year>.dat files
        scenario:           demand scenario name (e.g. 'Current Measure')
        validation_2021:    dat file name (in snapshot_dir) that fixes 2021 installed capacities
        validation_2023:    dat file name (in snapshot_dir) that fixes 2023 installed capacities
    """
    output_techs_dir.mkdir(parents=True, exist_ok=True)
    output_eud_dir.mkdir(parents=True, exist_ok=True)
    output_shares_dir.mkdir(parents=True, exist_ok=True)

    # Run snapshot models
    print(f'Running 2021 snapshot model ({validation_2021}) ...')
    res_2021 = _run_snapshot(_build_snapshot_model(snapshot_dir, validation_2021))
    print(f'Running 2023 snapshot model ({validation_2023}) ...')
    res_2023 = _run_snapshot(_build_snapshot_model(snapshot_dir, validation_2023))
    print('Running free snapshot model (no validation, for 2030-2050 bounds) ...')
    res_free = _run_snapshot(_build_snapshot_model(snapshot_dir, None))

    # Load prospective CSVs
    projected_demands      = pd.read_csv(prospective_dir / 'Data' / 'ESQC' / 'projected_demands.csv')
    prospective_param_ca   = pd.read_csv(prospective_dir / 'Outputs' / 'prospective_ratios_parameters_from_other_sources_for_ESQC.csv')
    prospective_param_estd = pd.read_csv(prospective_dir / 'Outputs' / 'prospective_ratios_parameters_from_ESTD_for_ESQC.csv')
    prospective_lyrios     = pd.read_csv(prospective_dir / 'Outputs' / 'prospective_ratios_lyrios_from_ESTD_for_ESQC.csv')
    for df in [prospective_param_ca, prospective_param_estd, prospective_lyrios]:
        df['Ratio 2020/2020'] = 1

    # Extract results
    eud_2021 = res_2021.parameters['end_uses_demand_year']
    eud_2021 = eud_2021[eud_2021.end_uses_demand_year != 0]
    eud_2023 = res_2023.parameters['end_uses_demand_year']
    eud_2023 = eud_2023[eud_2023.end_uses_demand_year != 0]

    df_filtered_2021 = _build_params_df(res_2021)
    df_filtered_2021 = df_filtered_2021[~df_filtered_2021['index0'].str.contains('FC_CH4')]
    df_filtered_2023 = _build_params_df(res_2023)
    df_filtered_2023 = df_filtered_2023[~df_filtered_2023['index0'].str.contains('FC_CH4')]

    bounds_2021 = _build_bounds_df(res_2021)
    bounds_2023 = _build_bounds_df(res_2023)
    bounds_free = _build_bounds_df(res_free)

    # Mobility sub-models
    mobility_sub_models = (
        [j for i in res_2021.sets['MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES'].values() for j in i]
        + [j for i in res_2021.sets['MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES'].values() for j in i]
        + [j for i in res_2021.sets['MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES'].values() for j in i]
    )
    transition_mob_maps = _load_transition_mob_maps(snapshot_dir / 'QC_data.dat')

    # Write EUD files
    print('Writing EUD dat files ...')
    _write_demand_file_2020(eud_2021, projected_demands, output_eud_dir, scenario)
    print('  QC_eud_2020.dat')
    for year in YEARS_2023:
        _write_demand_file_from_2023(year, eud_2023, projected_demands, output_eud_dir, scenario)
        print(f'  QC_eud_{year}.dat')

    # Write tech files
    print('Writing tech dat files ...')
    _write_techs_file(2020, df_filtered_2021, prospective_param_ca, prospective_param_estd,
                      prospective_lyrios, mobility_sub_models, transition_mob_maps,
                      output_techs_dir, df_bounds=bounds_2021, normalize_to_2025=False)
    print('  QC_techs_2020.dat')
    _write_techs_file(2025, df_filtered_2023, prospective_param_ca, prospective_param_estd,
                      prospective_lyrios, mobility_sub_models, transition_mob_maps,
                      output_techs_dir, df_bounds=bounds_2023, normalize_to_2025=True)
    print('  QC_techs_2025.dat')
    for year in [2030, 2035, 2040, 2045, 2050]:
        _write_techs_file(year, df_filtered_2023, prospective_param_ca, prospective_param_estd,
                          prospective_lyrios, mobility_sub_models, transition_mob_maps,
                          output_techs_dir, df_bounds=bounds_free, normalize_to_2025=True)
        print(f'  QC_techs_{year}.dat')

    # Extract share params from snapshot results (same approach as bounds)
    shares_2021 = _build_shares_df(res_2021)
    shares_2023 = _build_shares_df(res_2023)
    shares_free = _build_shares_df(res_free)

    print('Writing shares dat files ...')
    _write_shares_file(2020, shares_2021, output_shares_dir)
    print('  QC_shares_2020.dat')
    _write_shares_file(2025, shares_2023, output_shares_dir)
    print('  QC_shares_2025.dat')
    for year in [2030, 2035, 2040, 2045, 2050]:
        _write_shares_file(year, shares_free, output_shares_dir)
        print(f'  QC_shares_{year}.dat')

    print(f'\nDone.')
    print(f'  Techs  → {output_techs_dir}')
    print(f'  EUD    → {output_eud_dir}')
    print(f'  Shares → {output_shares_dir}')
