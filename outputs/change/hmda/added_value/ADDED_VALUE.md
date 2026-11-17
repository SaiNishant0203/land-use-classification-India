| model | rho-squared | AUC (cross-validated) | loss when left out (rho2 / AUC) |
|---|---|---|---|
| period and district dummies | 0.025 | 0.595 |  |
| + distance to the dense city | 0.171 | 0.796 |  |
| + land use within 1 km, from our map (shares, mix) | 0.199 | 0.818 |  |
| + tree cover on the cell | 0.208 | 0.823 |  |
| + accessibility (CBD, HITEC, airport, ORR, metro, major road, road km) | 0.224 | 0.835 |  |
| + supply constraints (terrain, lakes, restricted, GO 111) | 0.233 | 0.840 |  |
| + jobs and census (EC 2013, Census 2011, SECC, WorldPop) | 0.236 | 0.841 |  |
| final without distance to the dense city | 0.234 | 0.839 | 0.002 / 0.001 |
| final without land use within 1 km, from our map (shares, mix) | 0.221 | 0.829 | 0.015 / 0.012 |
| final without tree cover on the cell | 0.227 | 0.837 | 0.009 / 0.004 |
| final without accessibility (CBD, HITEC, airport, ORR, metro, major road, road km) | 0.224 | 0.831 | 0.012 / 0.010 |
| final without supply constraints (terrain, lakes, restricted, GO 111) | 0.226 | 0.836 | 0.010 / 0.005 |
| final without jobs and census (EC 2013, Census 2011, SECC, WorldPop) | 0.233 | 0.840 | 0.003 / 0.001 |
| final without distance to the dense city AND our-map land use | 0.194 | 0.812 | 0.043 / 0.028 |
