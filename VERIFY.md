# Verify version 1.0.0

Release date: 2026-11-04.

Supported execution: standard CPython 3.11+ on Linux or macOS, one sequential compute process. No package installation is needed. Do not use optimized Python for the certificate consumer: its assertions are part of the checker, and it explicitly rejects `-O`.

```sh
python3 -I -B verify.py --budget-seconds 540
# Optional: choose a NEW receipt path outside the sealed checkout.
python3 -I -B verify.py --budget-seconds 540 --output ../verification-receipt.json
# Hashes and file inventory only, without mathematical checks:
python3 -I -B verify.py --manifest-only
```

Run one full command, not both examples in succession. The maximum accepted budget is 600 seconds; the parent enforces the remaining wall time for each sequential child. A timeout, mismatch or rejected positive certificate is a failure, never a proof of the claim. The packet is not edited by verification.

Expected full result: `status: PASS`, 56 SBML-derived rules with 1,728 reference-comparison assignments and 1,728 certificate-to-model assignments, two M3 fixed points, 14 disjoint counterexample groups, candidate count 37, 70 saved induction/guard queries, 1,024 checked post-release cube assignments, and ROBDD counts:

| Set | States |
|---|---:|
| Phase 0 reachable | 24,344 |
| Phase 0 guard | 6,086 |
| Phase 1 reachable | 12,031,132 |
| Phase 1 release guard | 1,024 |
| Released reachable | 1,024 |
| Fair infinite avoidance, either phase | 0 |
| Phase 1 E1 states (controls maintained) | 3,997,780 |
| First-E1 reachable states | 3,997,780 |
| Largest released E1 invariant K | 14,336 |
| Size-14 candidates hitting all fourteen difference sets | 108 |
| Candidates excluded by unsafe released continuation | 107 |
| Successful size-14 sets | 1 |

`scripts/convert_model.py` regenerates the model, checks DNF against direct SBML evaluation and compares the recorded local truth-table hashes; see [MODEL-CONVERSION.md](MODEL-CONVERSION.md). `scripts/certificate_check.py` binds every recovered certificate function to the generated model before it consumes saved proof trees without generating certificates or calling a solver. `scripts/bdd_check.py` computes all fixed points and reachable sets from the frozen formulas; its `basic` mode also replays every trace. The two consumers' witness, sensor and initial-model inputs are cross-checked for equality. `scripts/kernel_audit.py` compares small-set operations and fairness against explicit finite graphs and checks corrupted inputs.

The full command includes semantic negative controls for altered trace bits, inconsistent release assignments, invalid proof steps, a shortened sensor set and a changed CNF function. Conversion controls reject altered SBML bytes, a changed derived formula and a changed reference truth-table hash. They run on temporary copies with the inner checker, so rejection is not merely a file-hash mismatch. A changed-file hash test and rejection of optimized Python are separate controls. The ROBDD audit additionally rejects legacy inadmissible paths and omission of the b2 clamp.

The manifest seals files, not mathematical truth or authorship. `verification/local.json` records the local clean-clone run; it does not mean that GitHub-hosted CI has run. The CI workflow executes the same full command. Source data and code identities are in `PROVENANCE.json`; the verification and independence boundaries are in `VERIFICATION-RECORD.md`.

`inputs/prior-witnesses.json` is an OLD b1-only protocol fixture for negative tests and exact comparisons. Its paths are not positive witnesses for the revised theorem. Only `inputs/witnesses.json` and `certificates/lower-result.json` contain the revised positive witnesses.

Uniqueness has only the ROBDD route; the saved-certificate consumer checks the lower and upper bounds, not the 107 exclusions. The uniqueness stage `scripts/unique_check.py` replays the lower witnesses, enumerates all 108 candidate sets, computes the largest released E1 invariant and all first-E1 states, and applies the complete protocol check to the surviving set. `verify.py` compares every classification row and deletion witness reference with `certificates/optimal-sets.json`, and binds the sole set to the S used by the other checks. The independent calculation and the full clean-clone replay for this augmented packet passed; see verification/local.json.

The prose-review revision was replayed in a new clean local clone on 2026-10-28. Its [receipt](verification/editorial-local.json) and [checked manifest](verification/editorial-input-manifest.json) are distinct from the earlier uniqueness-addition records. All six stages and negative controls passed; executable and mathematical bytes are unchanged by the subsequent receipt attachments.
