---
name: github-git-workflow
description: Use for creating branches, making commits, pushing changes, opening pull requests, checking CI, and resolving Git conflicts.
---

# GitHub Git Workflow

## Before changing code
1. Inspect repository instructions: AGENTS.md, CONTRIBUTING.md, README.md.
2. Check current state:
   ```bash
   git status
   git branch --show-current
   git log --oneline -5
   ```
3. Do not overwrite or discard existing user changes.

## Branches
- Create a dedicated branch from the default branch.
- Naming:
  - `feature/<short-description>`
  - `fix/<short-description>`
  - `docs/<short-description>`
  - `chore/<short-description>`
- Never commit directly to `main` unless explicitly instructed.

## Changes and verification
1. Keep scope limited to the requested task.
2. Run the repository's relevant tests, lint, formatter, and type checks.
3. Inspect changes before staging:
   ```bash
   git diff
   ```
4. Stage only related files:
   ```bash
   git add <file1> <file2>
   ```
5. Review exactly what will be committed:
   ```bash
   git diff --staged
   ```
6. Never commit secrets, `.env` files, keys, tokens, build output, or unrelated edits.

## Commits
- Make atomic commits: one logical change per commit.
- Use Conventional Commit style:
  - `feat: add profile validation`
  - `fix: prevent duplicate email registration`
  - `docs: explain local setup`
  - `test: cover invalid profile payload`
- Explain intent clearly; avoid messages like `update`, `fix`, or `wip`.

## Push and pull requests
- Before push, report:
  - changed files
  - tests/checks run and results
  - commit message
  - possible risks or follow-up work
- Ask for approval before `git push`, opening a PR, merging, force-pushing, rebasing shared branches, or deleting branches.
- Never force-push a shared branch.
- PR descriptions must summarize changes, tests, limitations, and any breaking change.

## Completion
Report:
- branch name
- commits created
- tests run
- files changed
- anything intentionally left out of scope
