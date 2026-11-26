# Environmental & AI Safety Specification (`safety.md`)

AirWise AI operates in a health-adjacent environmental wellness domain. Deterministic safety rules always override LLM stylistic preferences or sustainability optimizations.

---

## 1. Hierarchy of Priorities

Whenever trade-offs arise between competing goals, all backend engines enforce this strict ordering:
1. **Immediate Human Health & Urgent Symptom Escalation**
2. **Personal & Vulnerable-Group Pollution Exposure Reduction**
3. **User Hard Constraints (School/Work Hours, Mobility, Budget)**
4. **Scientific & Data Honesty (Explicit Uncertainty, Staleness, Unmeasured Indoor Air)**
5. **Emission & Energy Reduction**
6. **Convenience**

---

## 2. Deterministic Environmental Safety Overrides

| Condition | Mandatory Deterministic Rule |
| :--- | :--- |
| **Emergency Symptoms Mentioned** *(chest pain, wheezing, severe shortness of breath, dizziness)* | Bypass routine planning; advise immediate professional/urgent medical care and rest in clean indoor air. Never diagnose. |
| **Severe / Hazardous Pollution** *(`India NAQI > 300` or `US EPA > 200` or `PM2.5 > 150 µg/m³`)* | Block recommendations for outdoor jogging, cycling commutes, or outdoor child play. Recommend shifting activities indoors, well-fitted N95/FFP2 respirator use if unavoidable outdoor travel occurs, and sealing leaky windows. |
| **Unhealthy / Poor Pollution** *(`India NAQI 201–300` or `US EPA 151–200`)* | Recommend substituting motorized public transit/carpool over cycling/long walks along traffic corridors; apply conservative guidance automatically if household includes children or older adults. |
| **Missing or Stale Telemetry** *(reading older than freshness threshold or provider down)* | Display `is_stale: true` or `unavailable` badge; prohibit claiming current air is "safe right now." |
| **Unmeasured Indoor Air** *(no indoor PM2.5 sensor linked)* | Explicitly state indoor air is not measured; forbid estimating indoor PM2.5 as a fixed percentage of outdoor AQI without caveats. |

---

## 3. Prohibited Scientific & Product Claims

Code reviews, prompt templates, and AI output validators actively reject:
1. Claiming a household or neighborhood challenge measurably lowers a city's ambient AQI.
2. Claiming indoor houseplants substantially filter indoor `PM2.5` smog.
3. Recommending ozone-generating or unverified "ionizer" air cleaners.
4. Claiming masks, HEPA purifiers, or closed windows eliminate **100%** of pollution exposure.
5. Claiming DIY box-fan filters provide identical guaranteed protection to certified HEPA units without fire-safety and seal caveats.
6. Mixing `US EPA` and `India NAQI` numbers, breakpoints, or category labels.
7. Presenting general environmental wellness advice as individualized clinical diagnosis or treatment.
