# Governance

OdooPilot is the AI assistant for the Odoo ERP. It is open source under the licence in the LICENSE file. This document explains how decisions are made and how that will change as the project grows.

## Roles

- **Maintainer:** Arun Rajiah (@arunrajiah) leads the project. The maintainer reviews and merges pull requests, cuts releases, handles security reports and sets the roadmap.
- **Contributors:** anyone who opens an issue, reviews changes, improves documentation or submits a pull request.
- **Committers:** contributors who have made sustained, high-quality contributions can be invited to get merge rights for one or more areas.

## How decisions are made

- Day-to-day changes are decided in pull requests. A change needs one approving review from a maintainer or committer, plus passing CI where CI exists.
- Larger changes, such as a new tool that writes to Odoo records, a change to the confirmation and single-use token design, or a change to how access rules are applied, start as a GitHub issue labelled `proposal`. It stays open for at least 7 days so users can comment before work is merged.
- The maintainer makes the final call when consensus is not reached, and records the reasoning in the issue.

## Security decisions

Security issues follow [SECURITY.md](SECURITY.md). Security fixes may be merged without the 7-day comment period.

## Releases

Releases follow semantic versioning. Each release is tagged on GitHub with a changelog entry for every change that users will notice.

## Becoming a committer

A contributor can be nominated by the maintainer or by an existing committer after several merged contributions and constructive reviews. Committers who are inactive for 12 months may move to emeritus status, which can be reversed on request.

## Changing this document

Changes to this document follow the proposal process above.
