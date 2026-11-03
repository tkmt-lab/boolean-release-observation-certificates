# BioModels source and Boolean conversion

The bundled source is BioModels MODEL2004040001, `Selvaggio_etal_2020.sbml`, retrieved on 2026-10-26 UTC from the [official download endpoint](https://www.biomodels.org/model/download/MODEL2004040001?filename=Selvaggio_etal_2020.sbml). Its 210,053 bytes have SHA-256 `0be06df8664e0f6e187298753703110063d533384b14f22cabd4b569af06dd65`. A copy of the official JSON [model metadata](sources/model-metadata.json), omitting contributor email fields, and the original [file list](sources/files.json) are bundled; the latter independently supplies the same SHA-256. The URL can change in the future: the hash, bundled bytes and [retrieval record](sources/retrievals.json) pin this version. BioModels' terms cover the encoded model and its annotations under CC0.

`scripts/convert_model.py` reads 51 qualitative species and 41 transitions, with ten constant inputs. It accepts the MathML comparisons and Boolean combinations present in this file, rejects unsupported syntax and overlapping function terms, and evaluates each transition's target level. The source's default result level is zero.

For a species with maximum level m, threshold bit b_i denotes level at least i. On arbitrary Boolean words, decode the level as the length of the leading run of ones, denoted d. Thus 00 and 01 both decode to zero; 10 and 11 decode to one and two. On admissible words this is the ordinary threshold encoding. For multilevel output i, the next value is

```
(target >= i AND d >= i-1) OR d >= i+1.
```

This implements a one-level move toward the target on admissible states. Boolean species use the target directly. This convention explicitly defines the extension to inadmissible words; SBML itself does not define Boolean behavior on those words. The formula above uses all lower threshold bits when testing a prefix, including for the three-bit FA species.

The converter enumerates every assignment to each local dependency set (2,420 output evaluations, including 1,900 admissible cases), builds all prime implicants with Quine–McCluskey without don't-care states, and separately evaluates the resulting DNF on the same truth tables. Output order is alphabetical inputs followed by alphabetical internal bits. The generated file is [biomodels-derived.bnet](inputs/biomodels-derived.bnet), 56 rules, SHA-256 `e15ee45915ca1ff81b363cdf24db1a4f4fab37f250e6b3e57cf8ff9ca52d744d`.

During preparation, all 56 generated formulas were compared directly with the previously frozen PyBoolNet formulas on every assignment to the union of their local supports: 1,728 comparisons, with zero differences. This includes inadmissible threshold words. The smaller count reflects support reduction after minimization. The old file is omitted. [model-comparison.json](verification/model-comparison.json) retains its URL, commit, byte hash, variable order, local supports, assignment counts and truth-table SHA-256 values. Truth tables are encoded as one byte (0 or 1) per assignment in `itertools.product((0,1), repeat=len(support))` order, using the listed variable order. The full verification regenerates from SBML, validates the generated file, and compares all 56 generated truth-table hashes with that frozen comparison record. Offline replay relies on the recorded comparison; independently repeating the original two-file comparison requires obtaining the recorded reference separately. No reference formulas or truth-table bodies are bundled as that comparison record.

The saved proof certificates predate this source change. Their mathematical contents are unchanged. Because the new DNF uses a different term order, `certificate_check.py` decodes the conjunctions represented by the initial certificate's Tseitin clauses, checks all 56 recovered functions against the new model on 1,728 local assignments, then reconstructs and checks every expected CNF and replays the saved proof trees. Certificate encodings are therefore checked against the new model before use. Their clause numbering is retained so the saved reason indices remain meaningful. The ROBDD route reads only the newly derived model and the stated witnesses.

Normal verification is read-only:

```sh
python3 -I -B verify.py --budget-seconds 540
```

To deliberately regenerate the derived model in a development copy, use `python3 -I -B scripts/convert_model.py --build --output ../conversion-receipt.json`. The resulting bytes must match the recorded hash. `--reference PATH` additionally performs the preparation-time two-file comparison and replaces its record; it requires `--build` and is never invoked by `verify.py`. Modifying a sealed development copy requires rebuilding its manifest before normal verification.

This local formula correspondence does not establish equality of native multivalued paths, fairness or observation costs. The theorem continues to use the specified Boolean update protocol.
