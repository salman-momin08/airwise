# Environmental Methodology & Calculation Reference (`environmental-methodology.md`)

All environmental indices and impact calculations execute in deterministic, unit-tested Python modules (`backend/app/services/air_quality/` and `backend/app/services/impact/`).

---

## 1. Air Quality Index (AQI) Standards

Both supported standards use piecewise linear interpolation for each pollutant $p$:

$$I_p = \frac{I_{Hi} - I_{Lo}}{BP_{Hi} - BP_{Lo}} \times (C_p - BP_{Lo}) + I_{Lo}$$

$$\text{AQI} = \max_{p}(I_p), \quad \text{dominant\_pollutant} = \arg\max_{p}(I_p)$$

### 1.1 India National AQI (`india_naqi` — CPCB Standard)
- **Averaging Periods:** 24-hour average for `PM2.5`, `PM10`, `NO2`, `SO2`; 8-hour average for `CO` (`mg/m³`) and `O3` (`µg/m³`).
- **Validity Precondition:** At least **3 pollutants** must have valid sub-indices, and at least one **must** be `PM2.5` or `PM10` (unless computing an explicitly labeled single-pollutant indicative sub-index preview, which must never be labeled official NAQI).
- **Key PM2.5 / PM10 Breakpoints (`µg/m³`):**

| Category | AQI Range | PM2.5 (`µg/m³`) | PM10 (`µg/m³`) |
| :--- | :---: | :---: | :---: |
| **Good** | 0–50 | 0–30 | 0–50 |
| **Satisfactory** | 51–100 | 31–60 | 51–100 |
| **Moderate** | 101–200 | 61–90 | 101–250 |
| **Poor** | 201–300 | 91–120 | 251–350 |
| **Very Poor** | 301–400 | 121–250 | 351–430 |
| **Severe** | 401–500 | 250+ (251–380+) | 430+ (431–510+) |

### 1.2 US EPA AQI (`us_epa` — 2024 Revised PM2.5 Breakpoints)
- **Truncation Rules:** Truncate `PM2.5` (24-hr) to `0.1 µg/m³`; `PM10` (24-hr) to `1 µg/m³`; `CO` (8-hr) to `0.1 ppm`; `O3` (8-hr) to `0.001 ppm`; `SO2`/`NO2` (1-hr) to `1 ppb`.
- **Key PM2.5 / PM10 Breakpoints (`µg/m³`):**

| Category | AQI Range | PM2.5 (`µg/m³`, 2024 EPA) | PM10 (`µg/m³`) |
| :--- | :---: | :---: | :---: |
| **Good** | 0–50 | 0.0–9.0 | 0–54 |
| **Moderate** | 51–100 | 9.1–35.4 | 55–154 |
| **Unhealthy for Sensitive Groups** | 101–150 | 35.5–55.4 | 155–254 |
| **Unhealthy** | 151–200 | 55.5–125.4 | 255–354 |
| **Very Unhealthy** | 201–300 | 125.5–225.4 | 355–424 |
| **Hazardous** | 301–500 | 225.5–325.4+ | 425–604 |

---

## 2. Deterministic Impact Engine Formulas

Every calculation returns `is_estimate: true` alongside explicit `assumptions`, `source_references`, and `confidence`.

### 2.1 Transportation Emissions (`transport_co2e`)
For vehicle-based factors ($EF_{\text{vkm}}$ in $\text{kg CO}_2\text{e}/\text{vehicle-km}$) with occupancy $O \ge 1$:

$$EF_{\text{pkm}} = \frac{EF_{\text{vkm}}}{O}$$

$$\text{Emissions (kg CO}_2\text{e)} = \text{Distance (km)} \times EF_{\text{pkm}}$$

$$\Delta \text{Emissions} = \text{Emissions}_{\text{baseline}} - \text{Emissions}_{\text{alternative}}$$

### 2.2 Household Electricity & Energy (`household_energy_co2e`)
$$\text{Energy (kWh)} = \text{Power (kW)} \times \text{Operating Hours}$$

$$\text{Emissions (kg CO}_2\text{e)} = \text{Energy (kWh)} \times EF_{\text{grid}}\ (\text{kg CO}_2\text{e/kWh})$$

### 2.3 Indoor Air Filtration Effectiveness (`indoor_filtration_ach`)
Given room floor area $A\ (\text{m}^2)$, ceiling height $H\ (\text{m})$, and clean air delivery rate $\text{CADR}\ (\text{m}^3/\text{h})$:

$$V = A \times H, \quad \text{ACH}_{\text{purifier}} = \frac{\text{CADR}}{V}$$

Steady-state indoor-to-outdoor particle ratio approximation (when infiltration rate $\lambda_{\text{inf}}$, penetration factor $P$, deposition $k_{\text{dep}}$, and absence of indoor combustion sources are explicitly assumed):

$$\frac{C_{\text{in}}}{C_{\text{out}}} \approx \frac{P \cdot \lambda_{\text{inf}}}{\lambda_{\text{inf}} + k_{\text{dep}} + \text{ACH}_{\text{purifier}}}$$

*Constraint:* Never present this ratio as a guaranteed clinical health outcome or apply it when indoor smoke generation is active without noting source-control priority.

### 2.4 Relative Personal Exposure Comparison (`relative_exposure_index`)
Compares cumulative time-weighted concentration exposure ($\mu\text{g}\cdot\text{h}/\text{m}^3$) across two candidate routines using micro-environment modifiers ($M_{\text{env}}$, e.g., outdoor = `1.0`, sealed indoor / filtered transit = explicit range):

$$E = \sum_{i} C_i \times \Delta t_i \times M_{\text{env}, i}$$

*Constraint:* Report relative percentage/index change (`ug_h_per_m3`)—never label as exact biologically inhaled mass (`µg` deposited in lungs) unless validated ventilation-rate inputs are supplied.
