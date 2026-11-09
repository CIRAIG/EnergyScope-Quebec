# Excel workbooks of the critical materials project

## What these workbooks are for

These three workbooks are the **inputs** of the code: the pipelines in `src/` read them and generate the
`.dat` files of `ampl_files/` that `run_pathway(materials=True)` loads into the model.

The code treats them as **read-only**: any change (data, mapping, materials) is made by hand in Excel, then the
corresponding script is run again to regenerate the `.dat`. Each workbook has its own `Table of content` sheet
that describes all its sheets.

| Workbook | Pipeline | Script | Generated file | `run_pathway` option |
|---|---|---|---|---|
| `Material_intensities.xlsx` | `mi_pipeline` | `run_build_mi.py` | `Material_intensity.dat` | always loaded with `materials=True` |
| `Recycling_rates.xlsx` | `rr_pipeline` | `run_build_rr.py` | `Material_recycling.dat` | `materials_recycling=True` |
| `Material_limits.xlsx` | `limits_pipeline` | `run_build_limits.py` | `Material_limits.dat` | `materials_limit=True` |

The scripts rewrite the `.dat` files tracked by git: check the diff before committing.

---

# Material_intensities.xlsx

Material intensities of the EnergyScope-Québec technologies: source data (literature) + technology mapping
table. Output: `ampl_files/Material_intensity.dat`.

## Origin of the data

Most sheets come from the supplementary data of:

> Bieuville, P., Majeau-Bettez, G., de Bortoli, A. (2025). *Metal bottlenecks
> along energy transitions call for technology flexibility and sobriety.*

The sheets `Table of content`, `MI`, `Legend` and `Ref&Hp` document this data as published: do not modify
them.

## Sheets used by the pipeline

- **`Materials`**: master list of the materials (full name + short code). It is the only sheet to modify to add
  a material (see below).
- **`MI_Energy`**: material intensity of the electricity sub-technologies (t/GW).
- **`MI_H2`**: material intensity of the 3 electrolysers (Alkaline/PEM/SOEC), in t/GW.
- **`MI_Vehicles`**: intensity per vehicle (g/vehicle) and per powertrain (ICEV/HEV/PHEV/EV/FCV). Source:
  Watari et al. 2019 / Fishman et al. 2018. Used with `vehicle_source='watari'`.
- **`MI_Vehicles_2`**: default source (`vehicle_source='bieuville'`), rebuilt from the body + battery (per
  chemistry) + motor (per type), weighted by `MS_Battery_Motor_LDV`. FCV is not covered there: the value of
  `MI_Vehicles` is used in both cases.
- **`MI_Vehicles_Public`**: public transport (buses, etc.), in g/vehicle. Always used, whatever the source of the
  private vehicles.
- **`MS_Battery_Motor_LDV`**: market share per battery chemistry (per year) and per motor type (fixed).
- **`MS_Energy_Disag`**: market shares of the sub-technologies per decade, for the technologies of type
  `aggregate`.
- **`Mapping`**: one row per EnergyScope-Québec technology (710), with the literature sub-technology(ies) to
  use. `mapping_type`:
  - `direct` and `disaggregate`: a single sub-technology;
  - `aggregate`: several sub-technologies, weighted by `MS_Energy_Disag` according to `energy_source`;
  - `not_mapped`: no material intensity data.

The per-vehicle units are converted to t/(pkm/h) by the code, using the reference size of the vehicles
(`ref_size`, in `shared/data/Techs/out_techs.dat`).

## PV and wind

The 20 PV and wind sub-technologies (`PV_ROOF_C_SI`, `WIND_ONSHORE_DD_PMSG`, ...) are all `direct`. They only
exist in the model for `materials=True`, through `ampl_files/Subtechs*`. The 5 aggregated technologies
(`PV_ROOF`, `PV_GROUND`, `WIND_ONSHORE`, `NEW_WIND_ONSHORE`, `WIND_OFFSHORE`) are `not_mapped`.

---

# Recycling_rates.xlsx

Recycling rates, costs and recycling technologies. Outputs: `ampl_files/Material_recycling.dat` (rates and
costs) and `ampl_files/Material_recycling_process.dat` (recycling processes).

## For `run_build_rr.py` (`Material_recycling.dat`)

- **`Materials`**: same list of materials as in `Material_intensities.xlsx`.
- **`RR_Energy`, `RR_Vehicles`, `RR_H2`**: end-of-life recycling rates per material and sub-technology, one
  table per year (2020 to 2050).
- **`RR_Global`**: rates per material and per year, used for the technologies without a specific mapping.
- **`Mapping`**: same principle as in `Material_intensities.xlsx` (710 technologies: 180 `direct`, 530
  `not_mapped`).
- **`Cost_recycling_global`, `Cost_material_global`, `Cost_disposal_global`**: recycling cost, cost of the
  avoided primary material and landfill cost, per material (CAD/t). To be developed.

## For `run_build_rt.py` (`Material_recycling_process.dat`)

- **`Recycling_technologies`**: recovery rate per material and per recycling process. To be developed.
- **`Recycling_cost`**: cost of each process and revenue from the recovered material. To be developed.
- **`Collection_rate`**: share of the flow that is collected, per technology and per year. To be developed.

## Sheets not read by the pipelines

`Recycling_rates`, `RR_technology`, `Recycling_objective`, `Legend`, `Ref&Hp`, `Table of content`:
documentation or working data.

---

# Material_limits.xlsx

Annual production caps per material. Output: `ampl_files/Material_limits.dat`
(`limit_material_year`).

- **`Material_limits`**: caps in t/year per material, every 5 years (2020 to 2050). It is the only sheet read
  by the code (38 materials).
- **`Materials`**: list of the materials.
- The other sheets (`RoE_Demand`, `MiningCapacity_Calcul`, `Reserves_Resources_RR`,
  `MiningCapacity_Results`, `Calcul_Prod`, `Ref&Hp`) document how the caps are computed (demand of the rest of
  the economy, mining capacity, reserves): see `Table of content`.

Only the years 2030 to 2050 are written in the `.dat`: 2020 and 2025 stay at `Infinity` (default value of the
model).

---

# How to use them

**Regenerate an output file** — from `projects/critical_materials/`:
```bash
python run_build_mi.py [--vehicle-source watari|bieuville] [--no-dat]
python run_build_rr.py [--no-dat]
python run_build_rt.py [--no-dat]
python run_build_limits.py [--no-dat]
```
or in a notebook:
```python
from run_build_mi import main
main()
```
`--no-dat` (or `write_dat=False`) computes and prints the coverage report without writing the `.dat`.

**Add a material** — add a row to the `Materials` sheet (full name + short code) of the workbook(s) concerned,
then its values in the data sheets. No `.py` file to modify.

**Change the mapping of a technology** — edit its row in `Mapping` (`mapping_type`, `subtechs`,
`energy_source` for `aggregate`).

**Compare the two vehicle sources**:
```python
main(vehicle_source='bieuville')   # default
main(vehicle_source='watari')
```
Both write to the same output file (no suffix): `run_pathway` has to be run again between the two to compare
the results.

**Run the model with this data**:
```python
run_pathway('my_run', materials=True, materials_recycling=True, materials_limit=True)
```
