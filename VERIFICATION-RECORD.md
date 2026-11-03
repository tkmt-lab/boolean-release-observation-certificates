# Verification record and evidence boundary

Version 1.0.0, 2026-11-04. This record describes local verification and its evidence boundaries. Historical checks and hosted-CI status are recorded below.

## Historical checks

The producer constructed the revised lower paths, upper certificate and a separate AST-based certificate checker. A second research role built a ROBDD implementation from the frozen rules and permitted witness inputs. The corrected four-bit protocol was checked in internal review commit `93d54712a`: exactly two M3 fixed points, all 14 lower paths, the specified 14-bit upper bound, admissibility, all-prefix safety, both fair guards and E1 after release agreed. Three sequential Mac trials took 48.306 seconds in total, with peak RSS 321,126,400 bytes. This was the corrected protocol, not only the earlier b1-only version.

The reviewer had already read the earlier protocol's proof. During revised specification extraction, a brief certificate synopsis (including 70 queries and 1,024 assignments) was also displayed. The revised producer's code, proof body and actual invariant/certificate contents were not used in that ROBDD verification. These boundaries do not justify the phrase “fully proof-blind independent derivation.” No human peer review or Lean formalization is claimed.

## Packaging adaptations

After that review was completed, the producer certificate checker was read for this package. Its public adaptation adds an explicit `-O` rejection, checks phase switches before an update, requires phase-0 guard satisfaction before the switch, and ties each declared release assignment to the actual release frame. It consumes saved certificates only. It does not run the producer or SAT search.

The ROBDD and audit code are adapted from the reviewer implementation to use portable paths and explicit output receipts. RSS is reported in bytes on both macOS and Linux. The two approaches consume matching lower witnesses, sensor sets and initial-model lists. [Pinned internal source records and changes](PROVENANCE.json).

## Source migration and replay

The original packaging check passed in 46.505 seconds before the source change. That earlier receipt does not certify the revised package. The current model is generated from BioModels CC0 SBML; every local Boolean function agrees with the earlier reference. [Conversion convention and comparison](MODEL-CONVERSION.md). The source migration was performed by the same reviewer after reading the producer checker; no additional agent was used.

The saved CNF encodings are decoded and exhaustively checked against all generated model functions before reconstructing the expected CNFs. Certificate contents and proof indices remain unchanged. Conversion and CNF-binding negative controls accompany the existing controls. This source adaptation adds no claim of proof-blind derivation.

The local clean-clone source-migration replay passed on 2026-10-26 UTC with CPython 3.14.7 on macOS arm64. The candidate was committed to a local repository and cloned with `git clone --no-local`; the clone was clean before and after. Verification took 46.077680 seconds (46.196155 seconds including the validation subprocess wrapper). The receipt is [BioModels replay](verification/biomodels-local.json); the exact checked manifest is [BioModels input manifest](verification/biomodels-input-manifest.json), SHA-256 `0a943aeecd5360ed68ac7cef996113986f1d119d48da14a97fb731353bec1f66`. Local clone commit: `7737f411bb51c77a5ac75043569db90a986cc523`. This is a local validation identity, not a public repository URL. No hosted CI execution is represented as completed.

All five positive stages passed: model conversion, basic ROBDD checks, saved certificates, ROBDD all-path checks and kernel audit. The audit rejected nine damaged cases; five certificate mutations, three conversion mutations, optimized Python and a changed witness-file hash were also rejected. Peak reported RSS was 311,246,848 bytes. The final bundle adds the receipt and updates prose and metadata after the run; the final static check verifies that every executable, CI workflow, model source, comparison record and mathematical input is byte-identical to the checked clone. The final metadata copy omits contributor email fields from the original JSON; a separate parsed comparison verifies that every other metadata value is unchanged. Retrieval metadata and prose describe that transformation.

The full `verify.py` run regenerates the model in memory, checks the comparison record and saved proof trees, recomputes all fixed points and reachable sets with ROBDDs, checks fair avoidance, compares kernel operations to finite explicit cases, and rejects intentionally damaged inputs and certificates. The small finite comparisons are tests of the checker, not a formal proof of the implementation for every Boolean network.

## Scope and release gates

The claim is the fixed 56-rule, four-bit-clamp, 37-candidate-bit benchmark in [SPEC.md](SPEC.md). Written finite-set/fairness arguments combine the checked premises. Local formula correspondence is checked under the stated threshold convention. Native multivalued fairness/optimality, novelty and biological validity remain separate.

The model redistribution hold is resolved by bundling the BioModels CC0 source and the verified conversion, with the earlier bnet omitted. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). The owner authorized publication on 2026-10-26. The release metadata identifies version 1.0.0 dated 2026-11-04.

## Uniqueness addition and full packet replay

The reviewer used the same own ROBDD and the previous packet inputs to enumerate the 108 size-14 sets. No producer uniqueness-extension code, proof body or result data was read; only the request claim and directory filenames were seen. The final independent run passed in 55.071117 seconds, finding 107 unsafe candidates and one successful set. It also checks all fourteen single-bit deletions against the earlier witnesses. The [independent receipt](verification/uniqueness-local.json) is separate from the previous clean-clone receipt above. All six stages and all existing negative controls passed. Verification took 111.465899 seconds; the full wrapper including clone preparation took 111.810331 seconds, within the 600-second limit. One compute process was used, with zero cost and no publication. Maximum reported RSS was 337,559,552 bytes. The clone was clean before and after. Uniqueness-addition [receipt](verification/local.json), [checked manifest](verification/input-manifest.json), SHA-256 `9cfb1ca847e5f5ae78ee255dc2994122a7575767682a58bb007b955a4853a673`. Local clone commit: `542519d257c01953aae208e019dc31a566df8f81`. This local identity is not a public repository URL. Hosted CI has not been run. Receipt and prose additions were followed by a static check that every executable, CI workflow, model source and mathematical input remained byte-identical to the checked clone. [Detailed scope](OPTIMAL-SET.md).

The historical JSON keys `next15_code_or_proof_or_result_read` and `next15_code_proof_result_read` refer to whether the producer’s uniqueness-extension material was read at that earlier verification stage. These internal provenance keys and saved receipts are retained unchanged. They are not additional verification steps or theorem identifiers. Uniqueness has only the ROBDD implementation route, shared by `unique_check.py` and `bdd_check.py`; no separate certificate-consumer proof of uniqueness is included.

## Editorial review and replay, 2026-10-28

The nine required prose-review points were addressed without changing the mathematical claims, saved evidence values or verifier logic. Only the leading docstring of `unique_check.py` changed among executables; its remaining AST is identical to the input version. Historical receipts and internal provenance keys remain unchanged. No new agent review was performed for these edits.

The edited packet was committed to a local repository and cloned with `git clone --no-local --no-hardlinks`. One full `python3 -I -B verify.py --budget-seconds 540` run passed all six stages and existing negative controls in 96.484093 seconds. The clone was clean before and after, and matched the working packet byte for byte at replay time. Local clone commit: `6196d97c5642249ffc617130a23f89f6974d132f`. [Replay receipt](verification/editorial-local.json), [exact checked manifest](verification/editorial-input-manifest.json), SHA-256 `469e6d7a780dc431314a4546fe48fd3330832f09bfa3c067b63dabc3b41945df`. This local check did not publish the packet or execute hosted CI.

The final packet adds those two records and updates this explanation and replay metadata after the run. A final static check confirms that all executables, CI, mathematical inputs, source data and earlier receipts are byte-identical to the checked clone. These additions do not represent another full execution on the final manifest.
