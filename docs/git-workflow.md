# Beginner Git workflow

Git stores local version history. GitHub hosts it and coordinates Issues (tasks) and pull requests (reviewable changes). A branch isolates an assignment, a commit records a local checkpoint, and push uploads it. A PR requests review and is not automatically merged.

## Push access or a fork

Public cloning does not grant push access. GitHub handles/collaborator access are not yet configured. Teammates can start immediately with a **fork** and submit PRs; Anish can add collaborator access later when handles are supplied. No shared token is needed.

On GitHub, open https://github.com/AnishAwasthi/callup and click **Fork** to create `<your-handle>/callup`. If you already cloned the README's upstream repository:

```bash
git remote rename origin upstream
git remote add origin https://github.com/<your-handle>/callup.git
git remote -v
```

Replace `<your-handle>` with your actual handle. Otherwise, clone your own fork directly and add upstream:

```bash
git clone https://github.com/<your-handle>/callup.git
cd callup
git remote add upstream https://github.com/AnishAwasthi/callup.git
```

Your fork is `origin`; Anish's integrated repository is `upstream`. Collaborators who have push access can keep the README's direct clone and use `origin` as the shared repo.

## Update, branch, commit, push and PR

Start with saved/committed local work:

```bash
git status
git switch main
# Fork contributors:
git fetch upstream
git merge --ff-only upstream/main
# Direct collaborators instead use: git pull --ff-only origin main
git switch -c person-1/basic-hitting
# Work and run relevant tests/the offline example.
git diff
git add scripts/your_script.py docs/your_notes.md tests/your_test.py
git diff --cached
git commit -m "Add validated basic hitting features"
git push -u origin person-1/basic-hitting
```

Use your task's branch name and actual file paths. Avoid `git add .` until you understand what it includes. Raw data, API cache and full generated outputs belong outside Git. Never commit access tokens or `.env` secrets; inspect staged changes before each commit. Authenticate push with your own GitHub login (GitHub CLI `gh auth login` or Git credential manager); never use Anish's credentials.

On GitHub open a PR targeting **AnishAwasthi/callup, base main**, with your fork/task branch as the head (use “compare across forks” if needed). Direct collaborators select their shared-repo task branch. Link `Closes #<issue-number>`, describe behavior, schema, definitions, validation and limitations using the PR template. Request Anish's review, resolve comments with new commits and make checks pass. After approval, Anish integrates using squash-and-merge. Assignments should not push directly to main.

After merge, return to main and repeat the appropriate update commands above. If Git reports conflicts, unsaved work or a non-fast-forward update, ask for help; do not `reset --hard` or force-push main. To update a task PR, save/commit work, fetch upstream (or origin for direct collaborators), merge its main into the task branch, resolve files, rerun checks and push. Prefer this to rebasing while learning.

CI installs dependencies and runs lint, tests, the offline demo and a tracked-data guard. Standard hosted runners for public repos are [free under the current GitHub policy](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), checked October 6, 2026; this workflow uses standard ubuntu-latest and no paid add-ons. Checks do not approve scientific methodology. Branch protection is not automatically configured; use review before merging. Forked PRs need no dataset secrets or source records to run CI.
