# Synthetic predictive-energy validation

Independent training/held-out/test routes. Equal-weight empirical signed-error distributions.
Central 95% intervals have no guaranteed OOD coverage. Budgets concern aggregate electrical energy, not dynamic mission completion.

| Scenario | Model | CRPS Wh | Coverage 95% | Budget Brier |
| --- | --- | ---: | ---: | ---: |
| ID | M1 | 0.386 | 0.956 | 0.082 |
| ID | M2 | 0.617 | 0.933 | 0.108 |
| ID | M3 | 0.330 | 0.956 | 0.067 |
| ID | M4 | 0.347 | 0.956 | 0.072 |
| OOD-Combined | M1 | 20.560 | 0.000 | 0.321 |
| OOD-Combined | M2 | 52.351 | 0.000 | 0.896 |
| OOD-Combined | M3 | 20.499 | 0.000 | 0.293 |
| OOD-Combined | M4 | 20.611 | 0.000 | 0.325 |
| OOD-Mass | M1 | 0.752 | 0.667 | 0.091 |
| OOD-Mass | M2 | 1.883 | 0.467 | 0.082 |
| OOD-Mass | M3 | 0.664 | 0.600 | 0.077 |
| OOD-Mass | M4 | 0.751 | 0.578 | 0.085 |
| OOD-Rider | M1 | 0.961 | 0.489 | 0.183 |
| OOD-Rider | M2 | 3.528 | 0.200 | 0.559 |
| OOD-Rider | M3 | 0.964 | 0.489 | 0.193 |
| OOD-Rider | M4 | 0.982 | 0.444 | 0.191 |
| OOD-Route | M1 | 0.820 | 0.556 | 0.105 |
| OOD-Route | M2 | 1.425 | 0.578 | 0.131 |
| OOD-Route | M3 | 0.811 | 0.467 | 0.098 |
| OOD-Route | M4 | 0.851 | 0.511 | 0.110 |
| OOD-Slope | M1 | 0.392 | 0.956 | 0.085 |
| OOD-Slope | M2 | 2.620 | 0.267 | 0.119 |
| OOD-Slope | M3 | 0.324 | 0.956 | 0.063 |
| OOD-Slope | M4 | 0.389 | 0.911 | 0.086 |
| OOD-Temperature | M1 | 23.673 | 0.000 | 0.425 |
| OOD-Temperature | M2 | 23.783 | 0.000 | 0.463 |
| OOD-Temperature | M3 | 23.316 | 0.000 | 0.367 |
| OOD-Temperature | M4 | 23.704 | 0.000 | 0.422 |
| OOD-Wind | M1 | 1.240 | 0.467 | 0.077 |
| OOD-Wind | M2 | 8.978 | 0.067 | 0.250 |
| OOD-Wind | M3 | 1.271 | 0.400 | 0.091 |
| OOD-Wind | M4 | 1.258 | 0.378 | 0.073 |

All values are means across the declared seeds. Per-seed metrics and standard deviations are retained.
Raw energy samples are not clipped; negative/below-auxiliary fractions are reported in metrics.csv.
Reliability route-budget pairs are correlated. No real-world calibration, statistical significance or universal superiority is established.
