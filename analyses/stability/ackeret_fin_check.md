# Ackeret Fin Cross-Check (Mach 2.5, ramjet rocket)

**Purpose:** Independent closed-form hand-check of fin stability.

**Mach:** 2.50

**CG (nominal):** 1.6084 m from nose

**Body diameter (d_ref):** 0.200 m

## Component Breakdown

- **Body (slender-body potential):** CN_alpha = 2.000000 /rad, CP = 0.195333 m
- **Fins (pure Ackeret 2D):** CN_alpha = 21.614013 /rad, CP = 4.425253 m
- **Total:** CN_alpha = 23.614013 /rad, CP = 4.066998 m

## Static Margin

**SM = (CP - CG) / d_ref = (4.066998 - 1.6084) / 0.200 = 12.292991 cal**

**SIGN: POSITIVE (stable)**

## Comparison to DATCOM-class

This Ackeret check uses NO crossflow, NO finite-span correction, and NO fin-body interference. It should agree in SIGN with the DATCOM-class buildup at Mach 2.5 (same CG), even if the absolute values differ.

Reference: Ackeret 1925; Barrowman 1967.
