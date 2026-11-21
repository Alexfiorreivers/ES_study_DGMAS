# Public candidate readiness

The working tree has been reduced to code, synthetic examples, identifiers/hashes, aggregate tables and documentation. Full mixed-content evidence is preserved in a private editorial store, with pre-split hashes and a complete recovery snapshot. The history-free public export is the intended future upload source. No push, publication, commit or access-permission change has been made.

## Do not publish the current Git history

The pre-existing Git history includes data now withheld from this public candidate. A later deletion commit does not remove those objects. Use the history-free public export to create clean release history, or undertake a separately reviewed history-cleaning operation with backups. This task did not rewrite or delete the existing .git directory and did not inspect or alter remote visibility.

## Remaining release decisions

- Approve the reduced public scope and align the manuscript Data Availability wording: public code/identifiers/aggregates versus controlled editorial evidence. The Word manuscript was not edited during this rights task.
- For any later full-text release, finish source attribution, inherited ShareAlike and quotation/exception checks. Alternatively retain the current reduced public release; no separate permission is needed merely because the upstream datasets use ShareAlike, but its conditions must be met for content that is redistributed.
- If the actual DeepSeek service was a third-party reseller, review that provider's applicable contract before expanding output publication. The official API terms do not resolve an unidentified reseller contract.
- Submit full editorial evidence through the journal's controlled review channel, not as an automatically public supplement. Editorial routing is not a blanket legal exemption or a technical access control.
- Create a release tag and verify anonymous access only when publication is authorized. No study DOI has been assigned.

The supported public checks verify hashes, exact release contents, syntax/configuration contracts and frozen aggregate alignment. They do not reproduce the full experimental/audit pipeline. The previous full-evidence checks passed before the split and can be rerun on the private recovery snapshot. Runtime tests here use the available Python 3.12 interpreter; the platform declares Python 3.11, so a clean Python 3.11 installation remains a separate environment check.
