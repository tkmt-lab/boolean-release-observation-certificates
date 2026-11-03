# Frozen Boolean release-observation benchmark

This is a data-and-tools draft. It defines a finite computational result, not a claim about an intervention in cells.

The network is `inputs/biomodels-derived.bnet`, 56 Boolean rules derived from the bundled BioModels CC0 SBML, SHA-256 `e15ee45915ca1ff81b363cdf24db1a4f4fab37f250e6b3e57cf8ff9ca52d744d`. [Conversion and full local formula comparison](MODEL-CONVERSION.md). The variable order is the order of targets in this file. A stored state is a 14-digit hexadecimal integer with the first target as its least significant bit.

Ten environment inputs are fixed throughout:

```text
DELTA=0, ECM=1, EGF=0, FAT4_L=1, HGF=0, IL6=0,
ROS=0, RPTP_L=1, TGFB=0, WNT=0.
```

The readout is `(AJ_b1,AJ_b2,FA_b1,FA_b2,FA_b3)`. M3 means readout `(0,0,1,1,1)`. An unforced fixed point satisfies the natural rules under the fixed environment without intervention clamps. The initial set contains **every unforced fixed point** of the frozen rules with this environment and readout `(0,0,1,1,1)`. There are exactly two; their full values and an enumeration-completeness certificate are in `certificates/initial-fixed-points.json`. The reference xE is `xE` in `inputs/witnesses.json`, checked against all 56 rules. It is not asserted to be the only E1 fixed point. E1 means readout `(1,1,0,0,0)`. Safety means `AJ=00 or FA=000` at every prefix.

The corrected protocol is:

1. Atomically clamp `ECad=0, PAK=0, FAK_SRC_b1=0, FAK_SRC_b2=0`.
2. At the first state with `FA=000`, change only ECad to 1; retain the other three bit clamps.
3. For a selected set S, at the first state with E1 and `x|S=xE|S`, release **all four** clamps without an intervening update.

An update selects a single free bit and assigns its frozen natural function; self-updates are permitted. Inputs are never free. Controlled bits are not free during their clamp, and resume natural updates after release. Fairness means that on any infinite continuation within a phase every free bit is selected infinitely often. It does not impose a uniform waiting-time bound. Observations read values and do not control update times.

S is chosen once and remains fixed. Its guard uses only current values, not observation history. The optimum does not range over other guard formulas or interventions. S is chosen from the **37 bits** excluding the ten inputs, five readouts and four controlled bits. Cost is |S|. It is not the number of multivalued species measured, nor the number of interventions. Require, from every initial state and every fair update sequence, prefix safety, finite arrival at both guards, and E1 at every state following release. The minimum cost is **14**, under this exact specification.

One sufficient set is:

```text
PI3K, ITG_AB, SNAIL, p120_AJ, SLUG, AKT, RAP1,
RAS, HGFR, ERK, MEK, RAF1, miR200, NFkB.
```

These names denote variables in the frozen model, not recommendations for biological measurements.

The lower certificate has fourteen pairwise disjoint nonempty difference groups with admissible finite violation paths. The upper certificate has seventy UNSAT queries, phase invariants, a post-release invariant cube of 1024 assignments, and fair-convergence layer/rank premises. `scripts/certificate_check.py` reconstructs the queries and checks the stored proof trees rather than trusting a solver's verdict alone.

`certificates/lower-result.json` and `inputs/witnesses.json` contain the corrected paths. `inputs/prior-witnesses.json` is the explicitly labelled legacy b1-only protocol fixture for negative controls and comparison; it is not a positive certificate for this revised protocol. The reference target is stored in `inputs/witnesses.json`.

The upper result's `liveness_source` string is a legacy provenance label for the predecessor proof. The finite liveness premises actually consumed by `scripts/certificate_check.py` are bundled in `certificates/liveness.json`; no file outside this packet is read.

The multilevel threshold chains, written in increasing threshold order, are FAK_SRC (2 bits), ECad_AJ (2), AJ (2), FA (3). Admissibility requires nonincreasing bits along each chain. Natural single-bit updates and the corrected atomic clamps preserve this domain. The original b1-only FAK_SRC clamp can produce 01 and is a **different** Boolean protocol with 38 candidate observation bits. Its recorded optimum also equals 14, but it does not preserve the threshold domain.

The 56 functions are derived from the bundled 51-species SBML with the explicit threshold convention in MODEL-CONVERSION.md and agree with all earlier local Boolean truth tables. This package does not claim equality of all paths/fairness or observation costs with the native multivalued model, establish a clinical or cellular intervention, or establish universal membership of all fourteen bits in successful larger sets.

## Unique optimum and deletion necessity

Exactly one size-14 set satisfies this specification. The exhaustive 108-family classification and deletion witnesses are specified in [OPTIMAL-SET.md](OPTIMAL-SET.md). All 108 family guards are reachable; the 107 exclusions concern safety after release, not guard unreachability. Necessity means that deleting any one bit from the unique optimum fails. No claim about mandatory membership in all successful larger sets is included.
