# Git: your fork, branches, and pull requests

How the team shares code. Everyone works in **their own fork**, and changes reach the
team's `main` only through a **pull request** that someone else reviews.

> **The one rule:** pull first. Before you push, merge the team's latest `main` into your
> branch, run the tests, and only then push.

## The picture

```text
   AAV-2025-2026/ecolo-av          the team's repo: "upstream"
      main  ◄──────────────── pull request (reviewed, CI green)
        │                                ▲
        │ git pull upstream main         │
        ▼                                │
   your laptop  ── git push origin <branch> ──►  <you>/ecolo-av
   (branches, worktrees)                         your fork: "origin"
```

| Name | Where | You |
|---|---|---|
| `upstream` | `git@github.com:AAV-2025-2026/ecolo-av.git` | pull from it; never push to it |
| `origin` | `git@github.com:<you>/ecolo-av.git`, your fork | push your branches to it |
| `main` | the branch everyone shares | never commit on it; keep it equal to `upstream/main` |

## Set it up (once)

| # | Do this | You should see |
|---|---|---|
| 1 | An SSH key, if you have none: `ssh-keygen -t ed25519`, then add `~/.ssh/id_ed25519.pub` on GitHub (Settings, SSH keys) | `ssh -T git@github.com` says "Hi <you>!" |
| 2 | On GitHub, open `AAV-2025-2026/ecolo-av` and click **Fork** | `github.com/<you>/ecolo-av` |
| 3 | `git clone git@github.com:<you>/ecolo-av.git ~/ecolo-av && cd ~/ecolo-av` | the code |
| 4 | `git remote add upstream git@github.com:AAV-2025-2026/ecolo-av.git` | `git remote -v` lists `origin` and `upstream` |
| 5 | `git config pull.rebase false` | pulls merge, as this page assumes |
| 6 | `pixi install`, then `pixi run build && pixi run test` | [Your first day](first-day.md) |

Already cloned the team's repo? Turn it into this setup:

    git remote rename origin upstream
    git remote add origin git@github.com:<you>/ecolo-av.git

## Every change, step by step

| # | Step | Commands |
|---|---|---|
| 1 | Start from the team's latest `main` | `git switch main` then `git pull upstream main` |
| 2 | A branch for this change | `git switch -c <you>/<what>`, such as `ben/readme-commands` |
| 3 | Work, in small commits that each pass the tests | `tools/test.sh`, then `git add <files>` and `git commit` |
| 4 | **Pull first:** merge the team's latest `main` into your branch | `git fetch upstream` then `git merge upstream/main` |
| 5 | Fix any conflicts (below), then test again | `tools/test.sh`, and `pixi run test` before a pull request |
| 6 | Push the branch to your fork | `git push -u origin <you>/<what>` |
| 7 | Open the pull request | GitHub shows a **Compare & pull request** button; base: `AAV-2025-2026/ecolo-av` `main` |
| 8 | CI runs (about 15 min) and a teammate reviews | fix what they ask, commit, and push again: the pull request updates |
| 9 | Merged: tidy up | `git switch main`, `git pull upstream main`, `git branch -d <you>/<what>` |

Keep your fork's `main` current too, now and then: `git push origin main`.

!!! warning "Merge with a merge commit"
  On GitHub, merge a pull request with **Create a merge commit**. Never **Squash and
  merge** a branch that carries history (it turns every commit into one), and never
  force-push `main`.

## What a pull request needs

| Check | Why |
|---|---|
| `tools/test.sh` passes; `pixi run test` passes before you open it | CI runs the same; a red `main` blocks everyone |
| A new or changed feature has its row in [Features](features.md) | the report says who built what, and why |
| A new `pixi run` task has its row in the README's "Every command" | the front page lists every command |
| Docs changed: `pixi run docs`, and the HTML committed | the web pages match the markdown |
| No secrets: no passwords, keys or tokens | the repo is public |

The pull request's checklist reminds you of these.

## Conflicts

`git merge upstream/main` stops when you and someone else changed the same lines.

| # | Do this |
|---|---|
| 1 | `git status` lists the files "both modified" |
| 2 | In each, keep the right lines between `<<<<<<<`, `=======` and `>>>>>>>`, and delete the markers |
| 3 | `git add <file>` for each, then `git commit` (the merge's message is ready) |
| 4 | `tools/test.sh` again: a clean merge can still break a test |

- **`pixi.lock` in conflict:** take theirs, then let Pixi redo it:
  `git checkout --theirs pixi.lock && pixi install`, and commit the result.
- **Lost?** `git merge --abort` puts everything back as it was before the merge.

## Branches

| Do | Command |
|---|---|
| See your branches, and which you're on | `git branch` |
| Make one and switch to it | `git switch -c <you>/<what>` |
| Switch | `git switch <branch>` (commit or `git stash` your changes first) |
| Delete one that's merged | `git branch -d <branch>` |
| See what's on a branch and not on `main` | `git log --oneline upstream/main..<branch>` |

One branch per change: a pull request is easier to review when it does one thing.

## Worktrees: two branches at once

A worktree is a second folder on the same repo, with another branch checked out. Use one
to test a teammate's pull request, or to keep a long job running while you work on
something else.

    git worktree add ../ecolo-av-review -b review upstream/main    # a new folder and branch
    git worktree list                                              # every worktree
    git worktree remove ../ecolo-av-review                         # done: remove the folder

| Know this | Why |
|---|---|
| Each worktree has its own `build/`, `install/` and `.pixi/` | run `pixi install` and `pixi run build` in it once; Pixi reuses its download cache, so it's quick |
| A branch can be checked out in only one worktree | git refuses a second one |
| Commits made in any worktree are in the same repo | push them from wherever you are |
| Two runs at once on one computer | give each its own `ROS_DOMAIN_ID` (0-232), or their ROS nodes hear each other |

Claude Code's helpers make worktrees under `.claude/worktrees/`: git ignores that folder.

## Handy commands

| Do | Command |
|---|---|
| What changed, not yet committed | `git status`, `git diff` |
| The last commits, short | `git log --oneline -10` |
| Undo changes to one file (not yet committed) | `git restore <file>` |
| Put work aside, and bring it back | `git stash`, then `git stash pop` |
| Fetch everything, change nothing | `git fetch upstream` |
