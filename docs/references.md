# Verified academic references

Bibliographic targets verified online on 2026-10-01. References support modeling
concepts, not universal numerical defaults. Dataset values in this software are
assumptions or explicitly generated synthetic observations. No quoted experimental
result is used as a BikeEnergyLab validation result.

1. **Longitudinal cycling, aero and rolling power.** *Validation of a Mathematical
   Model for Road Cycling Power*, Journal of Applied Biomechanics 14(3), 276–291
   (1998). [Publisher DOI](https://doi.org/10.1123/jab.14.3.276),
   [institutional repository](https://collections.lib.utah.edu/details?id=705210).
2. **Electric bicycle coupled dynamics and energy.** *A simulation and experimental
   study of dynamic performance and electric consumption of an electric bicycle*,
   Energy Procedia 158, 2865–2871 (2019).
   [Publisher / DOI](https://doi.org/10.1016/j.egypro.2019.01.937).
   Title, journal, year and DOI verified in publisher indexed content. No
   unverified author list or experimental values are transcribed.
3. **Motor/system efficiency maps.** *Improving the Autonomy of a Mid-Drive Motor
   Electric Bicycle Based on System Efficiency Maps and Its Performance*, World
   Electric Vehicle Journal 12(2), 59 (2021).
   [Publisher](https://www.mdpi.com/2032-6653/12/2/59),
   [DOI](https://doi.org/10.3390/wevj12020059).
4. **ECM and SOC-dependent characterization.** Bor Yann Liaw, Rudolph G. Jungst,
   Angel Urbina, Thomas L. Paez, *Modeling of Battery Life I. The Equivalent Circuit
   Model (ECM) Approach*, Sandia National Laboratories, EESAT proceedings (2003).
   [Primary PDF](https://www.sandia.gov/ess-ssl/EESAT/2003_papers/Liaw.pdf).
   Explicitly chemistry-specific OCV/impedance. No universal coefficients imported.
5. **Physics–data models.** *Physics-guided Neural Networks (PGNN): An Application
   in Lake Temperature Modeling* (2017).
   [Author paper](https://arxiv.org/abs/1710.11431).
   Conceptual context only. This software uses a forest residual, not that network.
6. **Ensemble uncertainty.** Balaji Lakshminarayanan, Alexander Pritzel, Charles
   Blundell, *Simple and Scalable Predictive Uncertainty Estimation using Deep
   Ensembles*, NeurIPS 2017.
   [Author paper](https://arxiv.org/abs/1612.01474).
   Conceptual uncertainty context. Forest tree spread is not asserted equivalent
   to independent deep ensembles or a calibrated posterior.
7. **OOD and Mahalanobis support.** Kimin Lee, Kibok Lee, Honglak Lee, Jinwoo Shin,
   *A Simple Unified Framework for Detecting Out-of-Distribution Samples and
   Adversarial Attacks*, NeurIPS 2018.
   [Author paper](https://arxiv.org/abs/1807.03888).
   The current gate applies shrinkage covariance in route features. It does not
   reproduce the paper's class-conditional neural detector.
8. **Distribution-free uncertainty / conformal.** *A Gentle Introduction to
   Conformal Prediction and Distribution-Free Uncertainty Quantification* (2021).
   [Author tutorial](https://arxiv.org/abs/2107.07511).
   Split-conformal interpretation is limited by exchangeability. Shifts can
   invalidate coverage guarantees.

9. **Morris elementary effects.** Max D. Morris, *Factorial Sampling Plans for
   Preliminary Computational Experiments*, Technometrics 33(2), 161–174 (1991).
   [Publisher DOI](https://doi.org/10.1080/00401706.1991.10484804).
10. **Variance sensitivity.** Andrea Saltelli et al., *Variance based sensitivity
    analysis of model output. Design and estimator for the total sensitivity index*,
    Computer Physics Communications 181(2), 259–270 (2010).
    [Publisher DOI](https://doi.org/10.1016/j.cpc.2009.09.018).

CGPRA combines established tools into a testable provisional workflow. Establishing
academic novelty requires a dedicated systematic prior-art comparison and real
validation. References to concepts do not imply an endorsement of this implementation.
