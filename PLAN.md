# Plan: Codexlav Release

## Milestone 1: Release Shape

Exit criteria:
- README uses Codexlav name and positioning.
- SPEC defines runtime, required env keys, forbidden data, and release gates.
- PLAN exists in repo and matches release work.

## Milestone 2: Script Hardening

Exit criteria:
- requirement check validates `bash`, `python3`, `gcloud`, `codex`, and `systemctl`.
- GCP bootstrap sources explicit env values and can be rerun.
- Cloud Shell bootstrap creates the VM from a project id.
- VM setup script prompts for minimal required values and runs the setup chain.
- service installer writes a unit using the current clone path.
- release validation script checks shell syntax, Python syntax, executability, required files, and secret patterns.

## Milestone 3: Operator Docs

Exit criteria:
- README gives zero-to-run commands.
- GCP assistant prompt has placeholders, not private values.
- GCS artifact docs cover roles, lifecycle retention, and signed URL behavior.
- Telegram setup explains bot token, `/id`, private group, topics, and allowlists.
- git push instructions are safe and avoid embedded tokens.

## Milestone 4: Verification

Exit criteria:
- `scripts/validate_release.sh` passes.
- `git status --short` contains only intentional release files.
- no hardcoded private identifiers remain.
- manual service install path is documented and runnable on target VM.

## Current Owner

Single maintainer/operator.
