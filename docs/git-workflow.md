# Beginner Git workflow

Git stores local version history. GitHub hosts it and coordinates Issues (tasks) and pull requests (reviewable changes). A branch isolates your assignment. A commit records a local checkpoint; push uploads it. An Issue is not a branch and a PR is not automatically merged.

Start from a clean working tree; save your changes before switching branches:

```bash
git status
git switch main
git pull --ff-only origin main
git switch -c person-1/basic-hitting
# Work, run relevant tests and the sample example.
git diff
git add scripts/your_script.py docs/your_notes.md tests/your_test.py
git diff --cached
git commit -m "Add validated basic hitting features"
git push -u origin person-1/basic-hitting
```

Use your own task branch name. Avoid `git add .` until you understand what is included; the raw dataset, API cache and full generated outputs belong outside Git. Never commit access tokens or `.env` secrets. Inspect `git status` and `git diff --cached` before each commit.

Open GitHub → Pull requests → New pull request, with base `main` and your task branch. Link `Closes #<issue-number>`, describe resulting behavior, schemas, definitions, validation and limitations using the PR template. Request Anish's review; automated checks should pass. Address comments with additional commits on the same branch. Once approved and checks pass, use GitHub's squash-and-merge button, then delete the task branch if desired. Anish owns methodology review and integration. Do not push directly to main for assignments.

After merging:

```bash
git switch main
git pull --ff-only origin main
# Start the next task from this updated main.
```

If Git reports conflicting local work or a non-fast-forward update, stop and ask for help; do not use `reset --hard` or force-push main. For a PR that needs updating, commit/save local work, `git fetch origin`, and `git merge origin/main` on your task branch. Resolve files, rerun checks and push. Prefer that beginner workflow to rebasing until comfortable. Ask the reviewer about conflicts in shared contracts.

GitHub Actions installs dependencies and runs lint, tests, the offline demo and a tracked-data guard. Standard hosted runners for public repos are [free under the current GitHub policy](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), checked October 6, 2026; this workflow uses standard ubuntu-latest and no paid add-ons. These checks do not approve scientific methodology. Branch protection is not configured automatically; use review before merging. Forked PRs do not need dataset secrets or source records to run CI.
