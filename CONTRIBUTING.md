# Contributing guide

How every member pushes code without breaking each other's work.

---

## First time setup (do this once)

```bash
# 1. Clone the repo
git clone https://github.com/ThanyathipK/opd-system.git
cd opd-system

# 2. Create your virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate data and train models locally
python data/data_generator.py
python models/train.py
```

> opd.db and .pkl files are in .gitignore — every member generates these locally.
> Never commit them to GitHub (they are large binary files).

---

## Daily workflow — before you start coding

```bash
# Always pull latest changes from main first
git checkout main
git pull origin main

# Create or switch to your team branch
git checkout teamA/data-models        # Team A
git checkout teamB/dashboard          # Team B
git checkout teamC/docs-tests         # Team C

# Merge latest main into your branch to stay up to date
git merge main
```

---

## Saving your work

```bash
# 1. Check what you changed
git status

# 2. Stage your changes
git add data/data_generator.py        # specific file
git add .                             # all changes (be careful)

# 3. Commit with a clear message
git commit -m "feat: add no-show rate to data generator"

# 4. Push to GitHub
git push origin teamA/data-models
```

---

## Commit message format

Use short prefixes so everyone knows what changed at a glance:

| Prefix | Use for |
|--------|---------|
| `feat:` | new feature or file |
| `fix:` | bug fix |
| `docs:` | README, comments, CONTRIBUTING |
| `test:` | adding or fixing tests |
| `refactor:` | restructuring code, no behaviour change |

Examples:
- `feat: add triage classifier training script`
- `fix: handle empty patient list in scheduler`
- `docs: add API endpoint table to README`
- `test: add edge case for peak hour forecast`

---

## Opening a Pull Request (PR)

When your feature is ready to merge into `main`:

1. Push your branch to GitHub
2. Go to the repo on GitHub
3. Click **"Compare & pull request"**
4. Write a short description of what you changed
5. Tag one person from another team to review
6. Once approved → **Squash and merge**

---

## Branch names

| Team | Branch name |
|------|-------------|
| Team A | `teamA/data-models` |
| Team B | `teamB/dashboard` |
| Team C | `teamC/docs-tests` |

If you're working on a specific sub-task, you can create a sub-branch:
```bash
git checkout -b teamA/triage-classifier
```

---

## Rules

- Never push directly to `main`
- Never commit `opd.db`, `.pkl` files, or `venv/`
- Always pull before you start working
- One PR per feature — keep PRs small and focused
- If you break something, open an issue on GitHub so the team knows

---

## Resolving merge conflicts

If Git says there's a conflict:

```bash
# Open the conflicting file — look for markers like:
# <<<<<<< HEAD
# your code
# =======
# their code
# >>>>>>> teamA/data-models

# Edit the file to keep the correct version, then:
git add the_conflicting_file.py
git commit -m "fix: resolve merge conflict in data_generator"
```

When in doubt, ping the person who wrote the conflicting code on your group chat before resolving it.

---

## Useful Git commands

```bash
git log --oneline          # see recent commits
git diff                   # see what you changed (not yet staged)
git stash                  # temporarily save changes without committing
git stash pop              # bring back stashed changes
git checkout -- file.py    # discard changes to a file (careful!)
```
