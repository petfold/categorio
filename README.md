# categor.io

A website over [OntoDAG](https://github.com/petfold/ontodag).

- **New to it?** Read the [User Guide](docs/USER_GUIDE.md), a step-by-step
  tutorial for non-technical users. The site shows it at `/guide`, linked
  from every page.
- **The design**, and the reasons behind it: [docs/DESIGN.md](docs/DESIGN.md).
- **What's next:** [ROADMAP.md](ROADMAP.md).

## What it does

- **Anyone** can browse the public vocabulary: `core`, the ten domain
  packs, the dimension and unit packs. You can follow a category up and
  down, intersect categories (`artifact` and `container`) with "narrow by"
  suggestions, and download any pack as `.od`.
- **Each account has one OntoDAG store of its own**, at an address like
  `ada@categor.io`. You file your own things under the public vocabulary or
  under your own categories (`work`, `hobby`); your classifications are
  seen by no one else.
- **Sharing is filing.** File a category under someone's address, and they
  see it and everything under it. A group is a category filed under
  several people; `employees ⊑ sales` gives sales everything employees
  have. Members don't see each other, and a shared category's other parents
  stay hidden.
- **Receiving takes consent.** A share shows up as a request (name and
  count only) until you file the sender in your store. You can also block
  them.
- **Addresses tied to a category.** `ada+work@categor.io` puts what's sent
  to it into `work`, with its own setting for requests.
- **Pictures and a console.** Every category can be drawn as a picture of
  what you may see. The console runs the `odag` command language:
  questions anywhere, and changes on your own store, through the same
  checks as the buttons. Commands that touch the server's files or settings
  are refused, with the reason (DESIGN §12).
- **Your store as a whole:** history with undo and redo, and export and
  import as a self-contained `.od` file that `odag -f` reads directly. An
  export can include whole packs, merged into the file on the way out. An
  import shows whom it would share with before anything changes, and any
  change that would take something away from someone asks first.

## Run

Pictures need Graphviz's `dot` program (`apt install graphviz`, `brew
install graphviz`). Without it, everything else works and a picture says
why it can't be drawn.

```bash
python3 -m venv .venv && . .venv/bin/activate   # needs OntoDAG 0.28 or later
pip install -e ".[test]"
python -m categorio.app            # http://127.0.0.1:8000
pytest
```

Logins and account stores go in `data/` beside the code (ignored by git),
unless `CATEGORIO_DATA` names another folder.

For a deployment on Ubuntu, follow **[docs/DEPLOY.md](docs/DEPLOY.md)**
step by step (service account, gunicorn under systemd, nginx, HTTPS,
backups; the files are in `deploy/`). In short:

```bash
export CATEGORIO_SECRET_KEY=...        # required, or sessions reset on restart
export CATEGORIO_DATA=/var/lib/categorio
export CATEGORIO_SECURE_COOKIES=1      # behind HTTPS
export CATEGORIO_PROXY=1               # behind nginx: trust its X-Forwarded-* headers
gunicorn -w 1 --threads 8 'categorio:create_app()'
```

Use one worker process: writes are serialised inside it, and it holds one
shared copy of the public vocabulary (about 17 MB). User stores stay in
memory while recently used. `CATEGORIO_STORES_IN_MEMORY` sets how many
(default 500); the rest reload from disk when needed.

## Layout

- `categorio/names.py`: the three kinds of name, and addresses (DESIGN §3).
- `categorio/ontology.py`: the public store (every pack, merged), `.od` text,
  and the public ancestors a store keeps.
- `categorio/stores.py`: one `rs:` store per account: commit, undo and redo,
  and address registration (§10).
- `categorio/sharing.py`: the rule (§4), requests and settings (§6), and
  what an edit would take away (§9).
- `categorio/views.py`: what one viewer sees, combined per page from their
  store, the public store, and what's shared with them.
- `categorio/picture.py`: a category and its neighbours as SVG, drawn from
  the viewer's view.
- `categorio/console.py`: the `odag` commands allowed on the site, and how
  each runs.
- `categorio/app.py`: routes.
- `categorio/db.py`: SQLite for login records, registered addresses, and an
  index of which store mentions which address.

The data folder holds `logins.sqlite` and `stores/<username>/`, each an
ordinary OntoDAG record store.

## Licence

BSD 3-Clause, as OntoDAG; see [LICENSE](LICENSE).
