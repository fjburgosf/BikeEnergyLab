# Scientific method and assumptions

## Research question and hypothesis

Can calibrated physics, residual learning and confidence gating improve energy
prediction under new routes, riders and environments? H1: CGPRA preserves or
improves error relative to M1 physics, M2 data and M3 ungated residual hybrid,
especially under distribution shift. The implementation and protocol permit
refutation. No superiority, novelty or publication claim follows from its name.

The current study is synthetic, with an explicitly declared physical truth and
a separate nonphysical discrepancy term. Future validation must use real,
independent routes/riders and independent hardware characterization. Gating
can worsen results when real discrepancies persist outside the training domain.

## Dynamics, signs and fidelity

Movement is forward; speed is along-road m/s, positive wind acts forward,
grade is vertical rise / horizontal run and theta=atan(grade).
Froll=mg Crr cos(theta), Fgrade=mg sin(theta), Facc=ma.
Faero=0.5 rho CdA vrel |vrel|, vrel=v-wind. This signed form handles a tailwind
faster than the bicycle; squaring vrel without its sign would be wrong there.
Pwheel=(Froll+Fgrade+Faero+Facc)*v. Aerodynamic power at rest is zero even if
wind applies an aerodynamic force. Rolling force is zero at rest; static friction
is outside the model. Dry-air density is p/[287.05(T+273.15)] unless overridden.
Crosswind, rotating inertia and drivetrain gearing dynamics are not included.

The model uses inverse dynamics with prescribed speed, not a forward trajectory
solver. Acceleration is a center-interval finite difference when not supplied;
the first sample has zero inferred acceleration. Supply measured acceleration
when available and avoid treating the first interval as a standing start.
Segment merging is approximate for nonlinear aero/efficiency terms; conduct
segmentation convergence studies before inference from noisy routes.

## Bicycle and rider

Total mass is bicycle+rider+cargo. Crr can be a calibrated scalar for `default`
surface or an editable named-surface coefficient. Initial named values are only
illustrative assumptions; tires, pressure and roughness need measurement.
CdA, wheel radius and drivetrain efficiency are explicit. No universal coefficients
are claimed. Human input is pedal power; wheel contribution is eta_drive*Ppedal,
capped by positive demand. Unused human power is not charged into the battery.

Constant mode, temporal route columns and condition-dependent mode are available.
Condition mode optionally increases power with positive grade, scales by cadence
and applies exponential fatigue. Coefficients default to no grade/fatigue effect.
This is an operational model, not a validated physiological model.

## Assistance, motor and controller

Demand mode commands assist*demand; proportional mode caps command at
human_wheel*assist*assist_ratio. Default demand mode permits motor-only operation;
use proportional mode for a pedal-proportional controller. Assist is [0,1] and
brand independent. Limits are mechanical motor power, equivalent wheel torque
and configurable speed cutoff. No jurisdictional speed/power limit is assumed.

Motor shaft/equivalent-output power is wheel motor power/eta_drive. Electrical
motor power is shaft power/eta_motor. Constant efficiency is the simplest level.
CSV maps represent omega=v/r and equivalent output torque=(Pwheel/eta_drive)/omega, not a geared
mid-drive rotor speed unless the map has been transformed to this coordinate
system. Bilinear interpolation clamps points at map boundaries and exports an
outside-map flag. Temperature efficiency coefficients are user supplied and
default to zero. A configured response outside (0,1] is an error, not silently clipped.

## Battery and SOC

Energy/SOC modes use dSOC=Pterminal*dt/(3600*E_full), where
E_full=E_nominal*usable_fraction*empirical_temperature_multiplier. SOC is a
fraction on this effective full-capacity basis; available energy additionally
applies (initial_soc-soc_min). Thus a nominal 500 Wh battery with fraction 0.95
and SOC 0.90→0.10 has 380 Wh initially available, not 500 Wh.
The energy mode and SOC mode are equivalent representations in this version.
Temperature-varying energy modes use the local effective capacity approximation;
they do not represent thermal lag or reversible capacity release.

ECM: V=OCV(SOC)-R0 I-Vrc; dVrc/dt=-Vrc/(R1 C1)+I/C1.
Solve P=VI using the stable low-current quadratic root, cap discharge/charge
currents and voltage, count SOC by I dt/(3600 Qeffective), and use an exact
constant-current RC update per time step. Terminal energy and chemical power
OCV*I are distinct and exported. Capacity Ah must be characterized separately
from nominal Wh; changing Wh alone does not change ECM coulomb capacity.
The default linear pack OCV curve and R/C values are illustrative only.
ECM voltage is evaluated at the start of each small step; reduce timestep and
check convergence. No electrochemical/aging/thermal model is claimed.

Current, voltage, energy and SOC limits are explicit. A step reaching reserve
is shortened so distance/time stop at that point. Charging at SOCmax dissipates
available braking power instead of overcharging. No universal temperature slope
exists: capacity/resistance curves must be supplied with empirical provenance.
Temperatures outside those curves are rejected, not extrapolated.

## Regeneration and energy accounting

Regeneration defaults off. Enabled regeneration requires downhill/deceleration
power, minimum speed, an electrical power cap, battery charging current and SOC
headroom. Auxiliaries can be served by regenerative power even at a full battery.
There is no recuperation attributed to bicycles lacking this hardware.

The mechanical demand components are signed. The exact electrical balance adds
braking dissipation, drivetrain loss, motor loss, regeneration conversion loss
and auxiliaries, subtracts human wheel contribution and unmet wheel demand.
The exported `energy_balance_error_w` checks this identity. Electrical recovered
energy is shown separately; subtracting it again from signed grade energy would
double-count descent. A formula that mixes mechanical contributions and electrical
energy without efficiency/dissipation terms is insufficient.

## Calibration, identifiability and sequential updates

Fit weighted route terminal-energy errors with bounded SciPy least_squares.
Default unknowns are Crr and CdA; other constants are treated as known assumptions.
Optional motor efficiency, human power or auxiliary load require explicit bounds
and adequate independent excitation. The sensitivity Jacobian is normalized by
parameter spans for SVD rank/condition; column cosine measures confounding.
Report boundary estimates, collinear sensitivities and ill-conditioning.
Local covariance uses an approximate inverse Fisher matrix and residual variance;
under rank deficiency or robust loss it must not be interpreted as a calibrated
posterior. Recovery experiments use zero discrepancy/noise; the benchmark also
tests misspecification, where fitted physical parameters can absorb residual bias.

SequentialCalibrator implements bounded local-Jacobian RLS with forgetting,
observation variance and Joseph covariance updates in normalized coordinates.
Only newly observed routes may be consumed. CGPRAModel.adapt retargets and retrains
residuals after physical updates and invalidates conformal quantiles. Fresh
held-out interval calibration is required. This is not an EKF SOC observer.

## Residual learning and confidence

Training target is observed Wh/km minus calibrated physical Wh/km. Features
are time-weighted speed, speed cubed, acceleration, signed/positive slope, wind,
temperature, human power, mass, assist, Crr and speed variation. Route summaries
discard some sequence information; they are a fidelity limitation. M2 uses
scaled Ridge; residuals use seeded Random Forest, avoiding unmotivated deep learning.
A numerical scale floor of 1e-6 in each declared feature unit prevents floating-point
roundoff in nearly constant training columns from creating spurious enormous OOD
values. The floor is not an asserted sensor precision or test-driven hyperparameter.

The simple gate scales kNN support distance by the training 95th percentile of
leave-self-out neighbor distances. Advanced gate takes the larger normalized
kNN and shrinkage-Mahalanobis distance and additionally penalizes tree spread.
For support score d and spread u normalized by training residual SD:

`alpha = n/(n+20) * exp(-max(d-1,0)^2) / (1+u^2)`.

Simple mode sets u=0. Constants are specified before testing. Ensemble tree spread
is a heuristic, not a Bayesian standard deviation. Alpha is not probability of
correctness. OOD score measures feature support and cannot detect every conditional
shift. In OOD, alpha tends to zero and the prediction returns to calibrated physics,
which itself may be biased by calibration or missing physics.

## Predictive intervals and uncertainty propagation

Split conformal uses independent route groups and absolute Wh/km errors. Quantile
rank is ceil((n+1)*coverage); insufficient calibration samples are rejected.
All M1–M4 intervals use their own held-out scores. The finite-sample guarantee
requires exchangeability; OOD coverage is measured, never guaranteed. Interval
calibration routes do not enter physical calibration, residual fitting or gates.

Monte Carlo samples explicitly configured independent truncated-normal or uniform
physical/operating quantities. Mean, median, SD and central 95% intervals are
conditional on these assumptions. Model.predict_range returns this physical
uncertainty propagation; it does not silently add learned residual uncertainty.
CGPRA predictive intervals are a separate, observable error-calibration facility.
Operational profile columns override scalar settings; ambiguous scalar uncertainty
is refused when a route profile overrides it. Parameter correlations can be supplied
through a bounded joint Gaussian, including an explicitly approximate local
calibration covariance. Independent elevation noise at knots can be propagated
with a three-point median filter. OAT, Spearman, Morris and Sobol sensitivity are
implemented with explicit domains; [the global sensitivity protocol](global_sensitivity.md)
restricts variance attribution to independent bounded inputs. Chosen input distributions
are not automatically calibrated posteriors. Empirical signed held-out energy
errors alongside the physical priors; [its formulation and limitations](predictive_workflow.md)
distinguish energy-budget screening from dynamic mission completion.

Mission probability counts completed, power-feasible routes with final SOC above
the specified reserve. The Wilson interval represents Monte Carlo sampling error.
Route-specific range repeats the prescribed profile until reserve; incompatible
cycle transitions are a caller responsibility. Max-distance truncation is reported
as right censoring. A power-infeasible requested route has no admissible inferred
range and returns zero. Stationary-equivalent range is separately labeled.

## Validation and limitations

Train, conformal-calibration and test route groups are disjoint. Test categories:
ID, new morphology OOD-Route, Slope, Temperature, Rider, Mass, Wind and Combined.
Compare M1–M4, simple/advanced gates, and removal of calibration, residual, gating
and uncertainty penalty. Energy MAE/RMSE/R², Wh/km, SOC proxy, stationary range
error, coverage/width and calibration curves are saved. CRPS is available for
empirical predictive distributions; conformal sets alone do not define a CRPS
distribution. Three-seed repetitions summarize variability, without treating
segments as independent replicates or claiming significance from a small sample.

Current limitations include absence of real measured datasets, independent battery
and motor calibration, forward dynamics, crosswind, gearing, sequential validation
under real drift and peer-reviewed novelty
assessment. These are research limitations rather than hidden assumptions.
Timestamped GPX retains stationary intervals; discontinuous track segments require
explicit preparation rather than inventing a traveled bridge. Physical trajectory
bands interpolate endpoints on normalized route progress and report the number
of samples reaching each point, with no extrapolation after battery depletion.
The [causal drift protocol](adaptive_workflow.md) compares frozen and adaptive
models on declared synthetic data, with prediction before target ingestion.
