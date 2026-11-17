| model | rho-squared | AUC (cross-validated) | loss when left out (rho2 / AUC) |
|---|---|---|---|
| period and district dummies | 0.029 | 0.597 |  |
| + distance to the dense city | 0.186 | 0.775 |  |
| + land use within 1 km, from our map (shares, mix) | 0.275 | 0.843 |  |
| + accessibility (CBD, HITEC, airport, ORR, metro, major road, road km) | 0.285 | 0.846 |  |
| + supply constraints (terrain, lakes, restricted, GO 111) | 0.290 | 0.849 |  |
| + jobs and census (EC 2013, Census 2011, SECC, WorldPop) | 0.292 | 0.849 |  |
| final without distance to the dense city | 0.291 | 0.849 | 0.001 / -0.000 |
| final without land use within 1 km, from our map (shares, mix) | 0.221 | 0.805 | 0.072 / 0.044 |
| final without accessibility (CBD, HITEC, airport, ORR, metro, major road, road km) | 0.285 | 0.847 | 0.007 / 0.002 |
| final without supply constraints (terrain, lakes, restricted, GO 111) | 0.287 | 0.847 | 0.005 / 0.002 |
| final without jobs and census (EC 2013, Census 2011, SECC, WorldPop) | 0.290 | 0.849 | 0.002 / 0.000 |
| final without distance to the dense city AND our-map land use | 0.212 | 0.802 | 0.080 / 0.047 |
