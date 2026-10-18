# Working Together

## Branch and review flow

- Keep `main` as the working, demo-ready version.
- Make changes on a focused branch and open a pull request into `main`.
- Do not commit directly to `main`; review the diff and run the app before merging.
- Pull the latest `main` before starting each piece of work.

Example branch names:

- `feature/dashboard-and-price-comparison` — dashboard and market-price work
- `feature/pesticide-advisor` — pesticide model and its data interface

## Split of work

- Dashboard owner: login, app layout, market-price view, and integration.
- Pesticide-model owner: put model and recommendation logic in a separate `pesticide_advisor/` module. Avoid editing `app.py` until the module interface is agreed, which reduces merge conflicts.

Before integration, agree on a small interface such as `recommend(crop, problem, context) -> list[dict]`. Each result should include a product identifier, expected effectiveness, estimated cost per acre, and the source for its label claim. Safety and label checks must use verified product information; the model should not create application rates or safety claims.

## Keep local files out of commits

`.venv/`, the local SQLite account database, logs, and Streamlit secrets are ignored by Git. Decide together which data files belong in the repository before staging them. Never commit credentials, passwords, or private API keys.
