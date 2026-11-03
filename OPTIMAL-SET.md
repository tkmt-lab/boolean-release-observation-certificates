# A unique optimal observation set

For the fixed current-value equality guard in [SPEC.md](SPEC.md), the optimal additional observation set is uniquely

```
{AKT, ERK, HGFR, ITG_AB, MEK, NFkB, PI3K,
 RAF1, RAP1, RAS, SLUG, SNAIL, miR200, p120_AJ}.
```

These are variables in the frozen model, not recommendations for biological measurements.

Removing any one bit leaves 13 bits and therefore fails by the lower bound. The deletion certificate identifies the responsible finite counterexample; it adds a witness reference, not a separate lower-bound result. This does not assert that each bit belongs to every successful larger observation set, or optimize over different guards, histories or interventions.

The earlier fourteen finite counterexamples have disjoint difference sets. Any size-14 observation set meeting the requirements must choose exactly one bit from each difference set. Their product gives 108 sets; every other size-14 set misses a checked counterexample. The [classification certificate](certificates/optimal-sets.json) lists all 108 sets and the deletion-witness references.

The reviewer's ROBDD checker computes all states reachable in phase 1 with controls maintained, and separately all states reachable up to the first E1 state. Both have 3,997,780 E1 states in this instance. For the fully released network, it computes the largest subset K of the admissible E1 states closed under every free update:

```
K0 = admissible E1 states under the fixed inputs
K <- K intersect preimage_update(K), for every natural update
repeat until unchanged
```

Each step removes states with a transition outside the preceding set. Therefore a removed state has a finite continuation leaving E1. The remaining fixed point is closed under every released update; it contains 14,336 states. The checker verifies the closure again after convergence. No new biological or native multivalued equivalence claim follows from this finite Boolean calculation.

For each of the 108 sets S, the checker intersects its equality guard with the first-E1 reachable states outside K. This intersection is nonempty for 107 sets (between 192 and 1,760 states). Such a state is reached with no earlier E1, so this is a valid first release under that guard; its released continuation loses E1. A finite violating prefix can be extended with a fair schedule of natural updates. All 108 guards are reachable: their exclusion is about safety after release, not inability to reach a guard.

Only the set above survives this safety test. The checker then applies the full protocol verification to it, including prefix safety, all-fair-path finite switching and release, admissibility, and E1 preservation after release. That complete check passes. Together with the earlier lower bound, this proves uniqueness among all size-14 sets. For each one-bit deletion, one original difference group is missed; the associated finite trace establishes deletion necessity.

Uniqueness has one computational route. `unique_check.py` imports `bdd_check.py`; the separate saved-certificate consumer does not verify uniqueness. The 107 exclusions are recomputed as BDD sets, and individual counterexample paths for them are not bundled.

The independent calculation used the reviewer's own ROBDD and the previous BioModels-derived packet. The producer’s uniqueness-extension code, proof body and result data were not read. The reviewer already knew the earlier proof and the prior revised certificate synopsis; these historical boundaries remain as documented in [VERIFICATION-RECORD.md](VERIFICATION-RECORD.md). The current work is not a new agent review, a Lean formalization or human peer review.

The independent computation and the full clean-clone verification with this addition passed. The uniqueness-addition receipt is verification/local.json; the earlier BioModels-source replay is retained separately.

The subsequent prose-review replay also passed; see [the editorial receipt](verification/editorial-local.json) and [verification record](VERIFICATION-RECORD.md).
