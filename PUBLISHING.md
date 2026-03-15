# Publishing Cheri

## What was intentionally excluded

- `.venv/`
- `.wrangler/`
- local runtime state such as `state.json`, `credentials.json`, `tasks.json`, `task-runtime.json`, `task-logs.json`
- smoke-test files and other temporary artifacts
- internal audit reports and implementation notes from the working repository
- raw `wrangler_information` deployment snapshots

## Before pushing to GitHub

Check:

- `README.md` matches the files that are actually present
- `wrangler.toml` has safe values for public publication
- no session tokens, bootstrap secrets, or provider secrets exist anywhere in the folder
- `.gitignore` covers runtime residue and local overrides
- tests still pass from the cleaned folder

## Initialize git

```bash
cd cheri-app
git init
git add .
git commit -m "Initial Cheri public export"
```

## Add GitHub remote and push

```bash
git remote add origin <your-github-repo-url>
git branch -M main
git push -u origin main
```

## Verify after publishing

1. clone the published repo into a fresh directory
2. follow the install steps in `README.md`
3. run:

```bash
cheri --help
cheri config get
```

4. verify the backend instructions and invite test flow in the README still make sense for a new user
