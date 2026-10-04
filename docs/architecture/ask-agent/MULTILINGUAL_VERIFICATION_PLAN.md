# Ask agent — multilingual claim verification: findings and plan (2026-10-04)

📁 PROPOSAL — nothing here is implemented. The owner accepted the Phase 4 behaviour (cited
claims in English, explanation in the user's language) and asked for an evidence-based plan
before any change. Citation, claim and evidence verification must not be weakened.

## What exists

Every sourced claim is checked by `verify.judge`. That function uses the local NLI model
`cross-encoder/nli-deberta-v3-small`, which was trained on English. The answer contract
therefore asks for sourced blocks in English (A-58). The explanation follows the user's
language (V9).

## Measured (2026-10-04, zero Gemini, synthetic pairs written for this test — no client text)

Six clause/claim pairs, each with a true paraphrase and a false one (a changed figure, or
cash where the clause says credit), in English, Hinglish and Devanagari Hindi:

| Claim language | True claims SUPPORTED | False claims not passed | False claims CONTRADICTED |
|---|---|---|---|
| English | 6/6 | 6/6 | 6/6 |
| Hinglish (romanised) | 5/6 | 6/6 | 6/6 |
| Hindi (Devanagari) | 0/6 | 6/6 | 0/6 (all UNSUPPORTED) |

Reading:

- **Safety holds in every language.** No false claim passed. Devanagari fails closed
  (UNSUPPORTED), so it can never ship an unchecked claim; it can only lose true ones.
- **Hinglish is nearly as good as English** on this small set, because Hinglish legal text
  keeps the English terms and figures the model reads.
- **Devanagari is unusable** with the current model: 0/6.

Six pairs is a signal, not a decision. Every step below starts with a larger measurement.

## Options considered

| | Option | Verification of the text shown | New dependency | Verdict |
|---|---|---|---|---|
| A | Allow **Hinglish** sourced blocks when the user writes Hinglish | the shown text itself, same model | none | **recommended first**, after a 50-pair measurement shows ≥ 95 % of true claims supported and 100 % of false claims blocked |
| B | A **local multilingual NLI model** (an XNLI-trained multilingual cross-encoder) for Devanagari claims, run **in addition to** the English model | the shown text itself | a new self-hosted model — needs the owner's approval (rule 19, the `AM-83` precedent for model choice) | **recommended second**, only if a bilingual gold set shows it meets the same bar |
| C | Translate the Hindi claim to English with Gemini, then verify the translation | **not** the shown text — the check would pass on a sentence the reader never sees | none | **rejected**: it weakens verification |
| D | Show the verified English claim and a translated copy beside it | the translation is unverified | none | **rejected** for the same reason |

## Plan

1. **Measure Hinglish at scale (zero Gemini).** Build about 50 clause/claim pairs from the
   *supplied* documents' own clauses: true paraphrases, plus false ones with changed
   figures, negations, scope and party. Run `verify.judge` on all of them. Bar: true claims
   supported ≥ 95 % and false claims passed 0 %.
2. **If the bar holds, option A.** Change only `FINAL_INSTRUCTION`: when the reply language
   is Hinglish, sourced blocks may be in Hinglish. V2 (figures), V3 (negation), V4 (NLI),
   B5, X1 and X2 stay unchanged. Add a regression set of Hinglish claim pairs to the tests.
3. **Devanagari, option B, with owner approval.** Select a local multilingual NLI model by
   the same method (`AM-83`: measure, choose on material gain at acceptable cost). A claim
   in Devanagari would need SUPPORTED from the multilingual model **and** the figures and
   negation checks (V2, V3), which are script-independent once digits and number words are
   normalised. The English model keeps checking English and Hinglish.
4. **Never:** verify a translation in place of the shown text; relax V4 for any language;
   ship a claim the verifier could not read.

## Cost

Steps 1–2 need no Gemini calls and no new dependency. Step 3 needs a model download
(several hundred MB, local inference), the owner's approval, and a gold set of Devanagari
claims.
