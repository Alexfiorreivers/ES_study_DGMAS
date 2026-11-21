# Third-party rights and public release scope

Official-source review: 2026-11-21. This working tree is now the **public candidate**, with mixed full-text evidence moved to a separate private editorial store. No upload or public release has occurred. The old Git history still contains previously tracked evidence and must not be published as-is.

## Findings and decisions

| Material | Official terms and actual finding | Current routing |
| --- | --- | --- |
| 2WikiMultiHopQA | [Official Apache-2.0 notice](https://github.com/Alab-NII/2wikimultihop/blob/main/LICENSE); [release description](https://github.com/Alab-NII/2wikimultihop/blob/main/README.md) identifies Wikipedia paragraphs | Attribution and retained upstream license stay public. Mixed audited input files and replicated passages are held outside this public candidate. |
| MuSiQue | [Official README](https://github.com/StonyBrookNLP/musique/blob/main/README.md) declares CC BY 4.0 and identifies five seed datasets | MuSiQue's own licensed contributions may be shared with attribution and modification notices. This does not establish a single license for all inherited text. Mixed records are held for editorial review. |
| Wikipedia community text | [Wikimedia Terms section 7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en#7._Licensing_of_Content) allows reuse with attribution and applicable licensing; adapted text has ShareAlike requirements, with exceptions for separately sourced material | Not prohibited from publication. Full-text release is deferred until source attribution, applicable license/change notices and exceptional quoted material are resolved. Public metadata contains inferred title links, not a claim of per-page clearance. |
| MuSiQue seed components | [SQuAD](https://rajpurkar.github.io/SQuAD-explorer/) and [T-REx](https://hadyelsahar.io/t-rex/) identify CC BY-SA 4.0; [Natural Questions](https://ai.google.com/research/NaturalQuestions/download) and [MLQA](https://github.com/facebookresearch/MLQA/blob/main/README.md) identify ShareAlike 3.0 data terms | Exact inherited-component mapping is not established for every selected item. Zero Shot RE component terms remain unresolved here. Do not assume a seed's entire corpus was included or that every item has every seed's terms. |
| Recorded DeepSeek outputs | [API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html), section 4.2, assign any provider rights in output subject to law/terms; input and embedded third-party rights remain separate | No blanket provider ban on output publication was found. Full checkpoints are withheld because they combine prompts, passages and generated content, not because all generated output is forbidden. If a reseller was used, its contract must also be checked. |
| Qwen3-8B | [Official model license](https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE): Apache-2.0 | No weights are bundled. The model license does not clear source passages reproduced in checkpoints. |
| Project code, numerical aggregates, identifiers and synthetic schema examples | Author-approved Apache-2.0 software and CC BY 4.0 original non-software scope; facts and numerical values may not attract copyright | Retained in the public candidate. No third-party passage license is substituted by the project license. |

## Attribution and changes

2WikiMultiHopQA: Xanh Ho, Anh-Khoa Duong Nguyen, Saku Sugawara and Akiko Aizawa, COLING 2020, https://doi.org/10.18653/v1/2020.coling-main.580 . MuSiQue: Harsh Trivedi, Niranjan Balasubramanian, Tushar Khot and Ashish Sabharwal, TACL 2022, https://doi.org/10.1162/tacl_a_00475 . The authors' audited subsets involved selection, schema conversion, human corrections, added metadata and English localization. These are modified study derivatives, not unmodified official releases. Upstream license texts are retained in LICENSES/. No endorsement is implied.

The full audited pools have 7,338 document occurrences. Their core document objects provide titles and internal context locators, without dedicated URL/revision/license fields. Title-derived Wikipedia links are a useful attribution starting point, but do not alone resolve imported quotations, historical versions or every seed component. Missing revision IDs alone are not treated as a legal prohibition.

This is a release-scope assessment, not a finding that every withheld item is unlawful to distribute. ShareAlike is not a noncommercial restriction and does not automatically relicense unrelated project code. Existing licenses are not revoked by routing a local copy to editorial review. See docs/licensing/official_sources_20261121.json and file_routing_20261121.json for evidence and file-level decisions.

## Editorial copies

Full records are preserved unchanged outside this repository for controlled editorial verification. An English reading package distinguishes originals and translations. “Editorial only” is a delivery designation, not a new copyright license, a promise of confidentiality, or an automatic fair-use exemption. The authors should use the journal's controlled review channel and should not designate this full-text package as a public supplement without resolving the remaining rights. Any proposed onward publication needs its own rights check.
