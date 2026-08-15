# Ackeret Fin CP Hand-Check (Project B, ramP)

Independent closed-form cross-check of the fin center of pressure using pure Ackeret slender-body / thin-supersonic theory.

## Method

- **Fin-panel 2D slope**: `a_2D = 4 / sqrt(M^2 - 1)` [1/rad].
- **Finite-span correction**: `slope_fin = a_2D / (1 + 2/AR)` (classical low-AR downwash, NOT Puckett).
- **Fin-body interference**: `K_fb = 1 + R/(s+R)`.
- **CP location**: 50% of mean chord (supersonic uniform-pressure).

## Geometry

- Body diameter: 0.2000 m
- Total length: 4.35501 m
- Fin span (exposed): 0.5500 m
- Fin root chord: 0.1768 m
- Fin tip chord: 0.1768 m
- Fin sweep: 29.98 deg
- CG (config): 1.6084 m from nose

## Results at Ma 2.5 (cruise condition)

- **Nose CN_alpha**: 1.125000 [1/rad]
- **Transition CN_alpha**: 0.875000 [1/rad]
- **Fins CN_alpha (Ackeret)**: 7.589965 [1/rad]
- **Total CN_alpha**: 9.589965 [1/rad]

- **Nose CP**: 0.136538 m from nose
- **Transition CP**: 0.345381 m from nose
- **Fins CP (Ackeret)**: 4.425253 m from nose
- **Total CP**: 3.549891 m from nose

- **Static margin**: 9.707456 cal (STABLE)

## Comparison with DATCOM-class method

See `datcom_class_sweep.csv` for the DATCOM-class fin CP at Ma 2.5, CG = 0.37 L (config anchor).

**Agreement criterion**: Ackeret fin CP should be within ~one caliber (0.2000 m) of the DATCOM fin CP, and both should agree on sign (fins push CP aft, stabilizing).
