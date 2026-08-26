# LCA Objectives Modules — Documentation

This README documents the three AMPL model files:

- `QC_objectives_lca.mod` — global (territorial + abroad) life-cycle impacts, denoted **LCIA**
- `QC_objectives_lca_direct.mod` — direct (on-site combustion / process) impacts, denoted **DIRECT**
- `QC_objectives_lca_territorial.mod` — split of LCIA into **TERRITORIAL** (in-Québec) and **ABROAD** (outside Québec) impacts

All three files share the same structural pattern: a life-cycle-impact quantity is computed per technology/resource, phase and indicator, from construction, decommissioning, operation and resource-extraction contributions, then aggregated into phase totals, scenario totals, and compared against limits.

> **Note:** these files reference several sets, parameters and variables (`YEARS`, `TECHNOLOGIES`, `RESOURCES`, `PHASE`, `PHASE_WND`, `PHASE_UP_TO`, `PERIODS`, `PHASE_START`, `PHASE_STOP`, `years_active`, `lifetime`, `F_new`, `t_op`, `F_Mult_t`, `t_phase`) that are **not declared in these three files** — they must be declared in another `.mod` file that is included alongside these. They are listed below for completeness, marked "*(external)*".

> **Update (this revision):** the three bugs flagged in the previous review (undefined `y_inst`, undefined `y` in the resource constraint, and `Total*` variables incorrectly referenced with a phase index) have all been fixed — see the change log in §5.

---

## 1. Sets

| Set                                        | Declared in             | Description                                                                                            |
|--------------------------------------------|-------------------------|--------------------------------------------------------------------------------------------------------|
| `INDICATORS`                               | `QC_objectives_lca.mod` | Set of LCIA impact category indicators (e.g. `'TTHH'`, `'TTEQ'`, plus others used generically as `id`) |
| `YEARS` *(external)*                       | —                       | Reference years used to interpolate LCIA/impact factors                                                |
| `TECHNOLOGIES` *(external)*                | —                       | Set of technologies `i`                                                                                |
| `RESOURCES` *(external)*                   | —                       | Set of resources `r`                                                                                   |
| `PHASE` *(external)*                       | —                       | Set of model time phases                                                                               |
| `PHASE_WND` *(external)*                   | —                       | Subset of `PHASE`                                                                                      |
| `PHASE_UP_TO` *(external)*                 | —                       | Subset of `PHASE`                                                                                      |
| `PERIODS` *(external)*                     | —                       | Set of intra-year time periods `t`                                                                     |
| `PHASE_START[p]` *(external, indexed set)* | —                       | Start year associated with phase `p`                                                                   |
| `PHASE_STOP[p]` *(external, indexed set)*  | —                       | Stop year associated with phase `p`                                                                    |

---

## 2. Parameters

### `QC_objectives_lca.mod`
| Parameter         | Domain                            | Default | Description                                       |
|-------------------|-----------------------------------|---------|---------------------------------------------------|
| `lcia_op`         | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Operational LCIA factor per technology            |
| `lcia_constr`     | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Construction LCIA factor per technology           |
| `lcia_decom`      | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Decommissioning LCIA factor per technology        |
| `lcia_res`        | `{YEARS,INDICATORS,RESOURCES}`    | 0       | LCIA factor per resource                          |
| `limit_lcia_year` | `{YEARS,INDICATORS}`              | ∞       | Yearly cap on total LCIA per indicator            |
| `limit_lcia`      | `{INDICATORS}`                    | ∞       | Overall (pathway) cap on total LCIA per indicator |

### `QC_objectives_lca_direct.mod`
| Parameter           | Domain                            | Default | Description                                     |
|---------------------|-----------------------------------|---------|-------------------------------------------------|
| `direct_op`         | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Direct operational impact factor per technology |
| `limit_direct_year` | `{YEARS,INDICATORS}`              | ∞       | Yearly cap on direct impacts                    |
| `limit_direct`      | `{INDICATORS}`                    | ∞       | Overall cap on direct impacts                   |

### `QC_objectives_lca_territorial.mod`
| Parameter                | Domain                            | Default | Description                                                  |
|--------------------------|-----------------------------------|---------|--------------------------------------------------------------|
| `territorial_op`         | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Operational impact factor occurring within the territory     |
| `territorial_constr`     | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Construction impact factor occurring within the territory    |
| `territorial_decom`      | `{YEARS,INDICATORS,TECHNOLOGIES}` | 0       | Decommissioning impact factor occurring within the territory |
| `territorial_res`        | `{YEARS,INDICATORS,RESOURCES}`    | 0       | Resource impact factor occurring within the territory        |
| `limit_territorial_year` | `{YEARS,INDICATORS}`              | ∞       | Yearly cap on territorial impacts                            |
| `limit_territorial`      | `{INDICATORS}`                    | ∞       | Overall cap on territorial impacts                           |
| `limit_abroad_year`      | `{YEARS,INDICATORS}`              | ∞       | Yearly cap on abroad impacts                                 |
| `limit_abroad`           | `{INDICATORS}`                    | ∞       | Overall cap on abroad impacts                                |

### External parameters/variables referenced (not declared here)
`years_active[i,p_inst,p]`, `F_new[p_inst,i]`, `lifetime[y,i]`, `t_op[t]`, `F_Mult_t[y,i,t]` / `F_Mult_t[y,r,t]`, `t_phase` (used but never declared in these three files).

---

## 3. Variables

### `QC_objectives_lca.mod`
| Variable         | Domain                            |
|------------------|-----------------------------------|
| `LCIA_constr`    | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `LCIA_decom`     | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `LCIA_op`        | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `LCIA_res`       | `{PHASE,INDICATORS,RESOURCES}`    |
| `PhaseLCIA`      | `{PHASE,INDICATORS}`              |
| `TotalLCIA`      | `{INDICATORS}`                    |
| `TotalLCIA_REQD` | scalar                            |
| `TotalLCIA_RHHD` | scalar                            |

### `QC_objectives_lca_direct.mod`
| Variable           | Domain                            |
|--------------------|-----------------------------------|
| `DIRECT_op`        | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `PhaseDIRECT`      | `{PHASE,INDICATORS}`              |
| `TotalDIRECT`      | `{INDICATORS}`                    |
| `TotalDIRECT_REQD` | scalar                            |
| `TotalDIRECT_RHHD` | scalar                            |

### `QC_objectives_lca_territorial.mod`
| Variable                | Domain                            |
|-------------------------|-----------------------------------|
| `TERRITORIAL_constr`    | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `TERRITORIAL_decom`     | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `TERRITORIAL_op`        | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `TERRITORIAL_res`       | `{PHASE,INDICATORS,RESOURCES}`    |
| `PhaseTERRITORIAL`      | `{PHASE,INDICATORS}`              |
| `TotalTERRITORIAL`      | `{INDICATORS}`                    |
| `ABROAD_constr`         | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `ABROAD_decom`          | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `ABROAD_op`             | `{PHASE,INDICATORS,TECHNOLOGIES}` |
| `ABROAD_res`            | `{PHASE,INDICATORS,RESOURCES}`    |
| `PhaseABROAD`           | `{PHASE,INDICATORS}`              |
| `TotalABROAD`           | `{INDICATORS}`                    |
| `TotalTERRITORIAL_REQD` | scalar                            |
| `TotalTERRITORIAL_RHHD` | scalar                            |
| `TotalABROAD_REQD`      | scalar                            |
| `TotalABROAD_RHHD`      | scalar                            |

---

## 4. Equations

Notation: $p$ (phase), $y_{start}\in PHASE\_START[p]$, $y_{stop}\in PHASE\_STOP[p]$, $id\in INDICATORS$, $i\in TECHNOLOGIES$, $r\in RESOURCES$, $t\in PERIODS$, $p_{inst}$ (installation phase), $ys_{inst}\in PHASE\_START[p_{inst}]$, $ye_{inst}\in PHASE\_STOP[p_{inst}]$. All sums over $p, p_{inst}$ run over $PHASE\_WND \cup PHASE\_UP\_TO$.

### 4.1 `QC_objectives_lca.mod` (LCIA)

**Construction impact** (`lcia_constr_calc`)

$$
LCIA\_constr_{p,id,i} = \sum_{\substack{p_{inst},\, ys_{inst}\in PHASE\_START[p_{inst}] \\ ye_{inst}\in PHASE\_STOP[p_{inst}] \\ \text{s.t. } years\_active_{i,p_{inst},p} > 0}}
\frac{lcia\_constr_{ys_{inst},id,i} + lcia\_constr_{ye_{inst},id,i}}{2}
\cdot F\_new_{p_{inst},i} \cdot \frac{years\_active_{i,p_{inst},p}}{\dfrac{lifetime_{ys_{inst},i} + lifetime_{ye_{inst},i}}{2}}
$$

**Decommissioning impact** (`lcia_decom_calc`)

$$
LCIA\_decom_{p,id,i} = \sum_{\substack{p_{inst},\, ys_{inst}\in PHASE\_START[p_{inst}] \\ ye_{inst}\in PHASE\_STOP[p_{inst}] \\ \text{s.t. } years\_active_{i,p_{inst},p} > 0}}
\frac{lcia\_decom_{ys_{inst},id,i} + lcia\_decom_{ye_{inst},id,i}}{2}
\cdot F\_new_{p_{inst},i} \cdot \frac{years\_active_{i,p_{inst},p}}{\dfrac{lifetime_{ys_{inst},i} + lifetime_{ye_{inst},i}}{2}}
$$

**Operation impact** (`lcia_op_calc`)

$$
LCIA\_op_{p,id,i} = \frac{lcia\_op_{y_{start},id,i}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{start},i,t} \;+\; lcia\_op_{y_{stop},id,i}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{stop},i,t}}{2} \cdot t\_phase
$$

**Resource impact** (`lcia_res_calc`)

$$
LCIA\_res_{p,id,r} = \frac{lcia\_res_{y_{start},id,r}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{start},r,t} \;+\; lcia\_res_{y_{stop},id,r}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{stop},r,t}}{2} \cdot t\_phase
$$

**Phase aggregation** (`phaseLCIA_calc_r`)

$$
PhaseLCIA_{p,id} = \sum_{i\in TECHNOLOGIES} \left( LCIA\_constr_{p,id,i} + LCIA\_decom_{p,id,i} + LCIA\_op_{p,id,i} \right) + \sum_{r\in RESOURCES} LCIA\_res_{p,id,r}
$$

**Total aggregation** (`totalLCIA_calc_r`)

$$
TotalLCIA_{id} = \sum_{p} PhaseLCIA_{p,id}
$$

**Phase-level limit** (`phaseLCIA_limit`)

$$
PhaseLCIA_{p,id} \le t\_phase \cdot \frac{limit\_lcia\_year_{y_{start},id} + limit\_lcia\_year_{y_{stop},id}}{2}
$$

**Total-level limit** (`totalLCIA_limit`)

$$
TotalLCIA_{id} \le limit\_lcia_{id}
$$

---

### 4.2 `QC_objectives_lca_direct.mod` (DIRECT)

**Operation impact** (`direct_op_calc`)

$$
DIRECT\_op_{p,id,i} = \frac{direct\_op_{y_{start},id,i}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{start},i,t} \;+\; direct\_op_{y_{stop},id,i}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{stop},i,t}}{2} \cdot t\_phase
$$

**Phase aggregation** (`phaseDIRECT_calc_r`)

$$
PhaseDIRECT_{p,id} = \sum_{i\in TECHNOLOGIES} DIRECT\_op_{p,id,i}
$$

**Total aggregation** (`totalDIRECT_calc_r`)

$$
TotalDIRECT_{id} = \sum_{p} PhaseDIRECT_{p,id}
$$

**Phase-level limit** (`phaseDIRECT_limit`)

$$
PhaseDIRECT_{p,id} \le t\_phase \cdot \frac{limit\_direct\_year_{y_{start},id} + limit\_direct\_year_{y_{stop},id}}{2}
$$

**Total-level limit** (`totalDIRECT_limit`)

$$
TotalDIRECT_{id} \le limit\_direct_{id}
$$

### 4.3 `QC_objectives_lca_territorial.mod` (TERRITORIAL / ABROAD)

**Territorial construction impact** (`territorial_constr_calc`)

$$
TERRITORIAL\_constr_{p,id,i} = \sum_{\substack{p_{inst},\, ys_{inst}\in PHASE\_START[p_{inst}] \\ ye_{inst}\in PHASE\_STOP[p_{inst}] \\ \text{s.t. } years\_active_{i,p_{inst},p} > 0}}
\frac{territorial\_constr_{ys_{inst},id,i} + territorial\_constr_{ye_{inst},id,i}}{2}
\cdot F\_new_{p_{inst},i} \cdot \frac{years\_active_{i,p_{inst},p}}{\dfrac{lifetime_{ys_{inst},i} + lifetime_{ye_{inst},i}}{2}}
$$

**Territorial decommissioning impact** (`territorial_decom_calc`)

$$
TERRITORIAL\_decom_{p,id,i} = \sum_{\substack{p_{inst},\, ys_{inst}\in PHASE\_START[p_{inst}] \\ ye_{inst}\in PHASE\_STOP[p_{inst}] \\ \text{s.t. } years\_active_{i,p_{inst},p} > 0}}
\frac{territorial\_decom_{ys_{inst},id,i} + territorial\_decom_{ye_{inst},id,i}}{2}
\cdot F\_new_{p_{inst},i} \cdot \frac{years\_active_{i,p_{inst},p}}{\dfrac{lifetime_{ys_{inst},i} + lifetime_{ye_{inst},i}}{2}}
$$

**Territorial operation impact** (`territorial_op_calc`)

$$
TERRITORIAL\_op_{p,id,i} = \frac{territorial\_op_{y_{start},id,i}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{start},i,t} \;+\; territorial\_op_{y_{stop},id,i}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{stop},i,t}}{2} \cdot t\_phase
$$

**Territorial resource impact** (`territorial_res_calc`)

$$
TERRITORIAL\_res_{p,id,r} = \frac{territorial\_res_{y_{start},id,r}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{start},r,t} \;+\; territorial\_res_{y_{stop},id,r}\displaystyle\sum_{t} t\_op_t\, F\_Mult\_t_{y_{stop},r,t}}{2} \cdot t\_phase
$$

**Abroad impact = total (LCIA) − territorial** (`abroad_constr_calc`, `abroad_decom_calc`, `abroad_op_calc`, `abroad_res_calc`)

$$
ABROAD\_constr_{p,id,i} = LCIA\_constr_{p,id,i} - TERRITORIAL\_constr_{p,id,i}
$$

$$
ABROAD\_decom_{p,id,i} = LCIA\_decom_{p,id,i} - TERRITORIAL\_decom_{p,id,i}
$$

$$
ABROAD\_op_{p,id,i} = LCIA\_op_{p,id,i} - TERRITORIAL\_op_{p,id,i}
$$

$$
ABROAD\_res_{p,id,r} = LCIA\_res_{p,id,r} - TERRITORIAL\_res_{p,id,r}
$$

**Phase aggregations** (`phaseTERRITORIAL_calc_r`, `phaseABROAD_calc_r`)

$$
PhaseTERRITORIAL_{p,id} = \sum_{i\in TECHNOLOGIES} \left( TERRITORIAL\_constr_{p,id,i} + TERRITORIAL\_decom_{p,id,i} + TERRITORIAL\_op_{p,id,i} \right) + \sum_{r\in RESOURCES} TERRITORIAL\_res_{p,id,r}
$$

$$
PhaseABROAD_{p,id} = \sum_{i\in TECHNOLOGIES} \left( ABROAD\_constr_{p,id,i} + ABROAD\_decom_{p,id,i} + ABROAD\_op_{p,id,i} \right) + \sum_{r\in RESOURCES} ABROAD\_res_{p,id,r}
$$

**Total aggregations** (`totalTERRITORIAL_calc_r`, `totalABROAD_calc_r`)

$$
TotalTERRITORIAL_{id} = \sum_{p} PhaseTERRITORIAL_{p,id}
$$

$$
TotalABROAD_{id} = \sum_{p} PhaseABROAD_{p,id}
$$

**Phase-level limits** (`phaseTERRITORIAL_limit`, `phaseABROAD_limit`)

$$
PhaseTERRITORIAL_{p,id} \le t\_phase \cdot \frac{limit\_territorial\_year_{y_{start},id} + limit\_territorial\_year_{y_{stop},id}}{2}
$$

$$
PhaseABROAD_{p,id} \le t\_phase \cdot \frac{limit\_abroad\_year_{y_{start},id} + limit\_abroad\_year_{y_{stop},id}}{2}
$$

**Total-level limits** (`totalTERRITORIAL_limit`, `totalABROAD_limit`)

$$
TotalTERRITORIAL_{id} \le limit\_territorial_{id}
$$

$$
TotalABROAD_{id} \le limit\_abroad_{id}
$$