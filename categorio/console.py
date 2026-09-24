"""The `odag` command language on the site, restricted to what is safe here.

OntoDAG's own browser app runs a subset of its CLI over an in-memory
sandbox. This is the same idea over real stores, so the subset is narrower
and every write goes through the site's rules:

- **Reads** run on one store: your own, or the public vocabulary. Visitors
  get the public vocabulary only.
- **Writes** (`put`, `move`, `remove`) run on your own store only. They are
  tried on a copy first. If the result names an address of another site,
  it is refused. If it would stop someone seeing something, it waits for a
  confirmation — the same check the pages make (DESIGN §9).
- **Versions** (`history`, `status`, `undo`, `redo`) use your store's
  history, the one the Store page shows.
- **Vocabulary** (`pack`, `prelude`): looking only. `pack` lists the packs,
  `pack biology --show` shows one, `--diff` previews what it would add to a
  store. Adopting (`pack biology`) is refused: the site holds one copy of
  every pack, shared by all stores, and copying one into a store would put
  a second copy on disk and in memory for each user who did it. To take a
  whole pack away with you, Store → Export can include it in the file.
- **Everything else is refused, with the reason.** Commands that read or
  write server files (`import`, `export`, `-o FILE`, …), change which store
  or node the server uses (`set`, `swarm`, `index`), or are the site itself
  (`web`).

What a line touches comes from OntoDAG itself: every command declares its
effects (`COMMAND_EFFECTS`, OntoDAG 0.27), and a command without them fails
OntoDAG's own suite. So a command added later runs here only if it declares
nothing beyond reading or writing a store; the site keeps no list of its own
that could fall behind.
"""

import io
import shlex
from collections import OrderedDict, deque

from ontodag.__main__ import COMMAND_EFFECTS, PARSER, dispatch, effects as _effects

from categorio import names, ontology

# What may run is decided by what a line touches, as OntoDAG declares it
# (`ontodag.__main__.COMMAND_EFFECTS`, sharpened per line by `effects`):
#   only `reads`             anyone, on the public vocabulary or their store
#   `writes` / `versions`    your own store only
#   `files`, `network`, `settings`   nowhere — they act on the server
# One policy of the site's own on top: adopting a pack (`pack NAME`,
# `prelude`) is refused, since it would copy the shared vocabulary into a
# store (DESIGN §2).
ON_A_STORE = frozenset({"reads", "writes", "versions"})
VOCABULARY = {"pack", "prelude"}


def touches(tokens):
    """The line's effects, or None for a command OntoDAG does not have."""
    try:
        return _effects(tokens)
    except ValueError:
        return None


def adopts(tokens):
    """`pack NAME` and `prelude` change the store; listing, `--show` and
    `--diff` only look."""
    touched = touches(tokens)
    return tokens[0] in VOCABULARY and touched is not None and "writes" in touched

REFUSED = {
    "import": "reads a file on the server — use Store → Import, which previews first",
    "merge": "reads a file on the server — use Store → Import, which previews first",
    "ingest": "reads a stream from the server — not available here",
    "export": "writes a file on the server — use Store → Export to download yours",
    "excerpt": "writes a file on the server — use Store → Export",
    "diff": "compares two stores by file path, and the site has no files for you to name",
    "visualize": "writes an image on the server — every page has a Picture instead",
    "index": "publishes a record store from the server — not available here",
    "set": "changes the server's settings, which no page may do",
    "swarm": "talks to a Swarm node from the server — not available here",
    "web": "is what you are looking at",
}

GROUPS = (
    ("Filing things", ("put", "move", "remove")),
    ("Asking questions",
     ("get", "count", "list", "show", "below", "overlapping", "overlaps", "meet", "canon")),
    ("Versions", ("history", "status", "undo", "redo")),
    ("Vocabulary", ("prelude", "pack")),
    ("Files and pictures",
     ("import", "export", "merge", "ingest", "excerpt", "diff", "visualize")),
    ("Store and network", ("set", "index", "swarm", "web")),
    ("Help", ("help",)),
)

OUTPUT_LIMIT = 20_000


class Stream(io.StringIO):
    """Says it is a terminal, so the CLI shows readable spellings and caps
    long answers — a browser is a person (the choice OntoDAG's own web
    console makes)."""

    def isatty(self):
        return True


class Session:
    """What `dispatch` needs: one DAG, and nothing else. `view()` is the DAG
    itself — never the server's `overlays` setting, which would compose
    other stores into the answer."""

    spec = "categor.io"

    def __init__(self, dag):
        self.dag = dag

    def view(self):
        return self.dag

    def save(self):
        pass

    def describe(self):
        return self.spec


class Result:
    def __init__(self, line, out="", err="", code=0, losses=None, scope="mine"):
        self.line, self.out, self.err, self.code = line, out, err, code
        self.losses = losses or {}
        self.scope = scope


def refusal(tokens, scope, signed_in):
    """Why this line may not run here, or None."""
    command = tokens[0]
    touched = touches(tokens)
    if touched is None:
        return "is not a command here (try `help`)"
    if "files" in touched and "files" not in COMMAND_EFFECTS.get(command, ()):
        return "with -o would write a file on the server, which is not available here"
    if not touched <= ON_A_STORE:
        return REFUSED.get(command) or (
            "touches the server's " + ", ".join(sorted(touched - ON_A_STORE)) + ", which no page may")
    if adopts(tokens):
        return ("would copy the whole pack into your store — a second copy of what "
                "every store here already shares. To use it, just file under its "
                "categories; to take it away with you, include it in Store → Export")
    if touched <= {"reads"}:
        return None
    if not signed_in:
        return "needs an account — sign in to run it on your own store"
    if scope != "mine":
        return "changes a store — switch to “your store” to run it"
    return None


def _run(tokens, dag):
    out, err = Stream(), Stream()
    try:
        code = dispatch(tokens, Session(dag), out=out, err=err)
    except Exception as exc:                      # a bug should not take the page down
        return "", f"odag: {type(exc).__name__}: {exc}\n", 1
    text, note = out.getvalue(), err.getvalue()
    if len(text) > OUTPUT_LIMIT:
        text = text[:OUTPUT_LIMIT] + "\n…\n"
        note += "odag: the answer is cut short here; narrow the question\n"
    if tokens[0] == "help":
        note += ("odag: on this site: " + " ".join(sorted(n for n, e in COMMAND_EFFECTS.items() if e <= ON_A_STORE))
                 + " — see the list of commands below\n")
    return text, note, code


class Console:
    def __init__(self, site):
        self.site = site
        self.transcripts = OrderedDict()     # browser session -> its recent Results

    def transcript(self, key):
        if key not in self.transcripts:
            self.transcripts[key] = deque(maxlen=12)
            while len(self.transcripts) > 2000:  # in memory only; the oldest go first
                self.transcripts.popitem(last=False)
        self.transcripts.move_to_end(key)
        return self.transcripts[key]

    def run(self, user, scope, line, confirm=False, context=None):
        """Run one line. `scope` is 'mine' or 'public'; visitors are 'public'.
        `context(dag, names)` brings in public ancestors before a write."""
        if user is None or scope != "mine":
            scope = "public"
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            return Result(line, err=f"odag: {exc}\n", code=1, scope=scope)
        if not tokens:
            return Result(line, scope=scope)
        why = refusal(tokens, scope, user is not None)
        if why is not None:
            return Result(line, err=f"odag: `{tokens[0]}` {why}\n", code=2, scope=scope)

        command = tokens[0]
        touched = touches(tokens)
        if scope == "public":
            return self._read_public(line, tokens)
        if "versions" in touched:
            return self._versions(user, line, command)
        if "writes" in touched:
            return self._write(user, line, tokens, confirm, context)
        stores = self.site.stores
        dag = stores.get(user)
        before = len(dag.nodes)
        out, err, code = _run(tokens, dag)
        if len(dag.nodes) != before:                  # a read must not change anything
            stores.reload(user)
        return Result(line, out, err, code, scope=scope)

    def _read_public(self, line, tokens):
        dag = ontology.public()
        before = len(dag.nodes)
        out, err, code = _run(tokens, dag)
        if len(dag.nodes) != before:
            ontology.reset_public()                  # never let a query alter the vocabulary
        return Result(line, out, err, code, scope="public")

    def _write(self, user, line, tokens, confirm, context):
        stores, sharing = self.site.stores, self.site.sharing
        own = stores.get(user)
        trial = own.deepcopy()
        if context:
            context(trial, tokens)
        out, err, code = _run(tokens, trial)
        if code:
            return Result(line, out, err, code)
        for name in set(trial.nodes) - set(own.nodes):
            if names.is_address(name) and names.parse_address(name) is None:
                return Result(line, err=f"odag: {name!r} is not a {names.DOMAIN} address\n", code=2)
        if "--dry-run" in tokens:
            return Result(line, out, err, code)
        losses = sharing.losses(own, trial, user)
        if losses and not confirm:
            return Result(line, out, err, code, losses=losses)

        result = {}

        def change(dag):
            if context:
                context(dag, tokens)
            result["run"] = _run(tokens, dag)
        stores.edit(user, change, f"console: {line}")
        out, err, code = result["run"]
        return Result(line, out, err, code)

    def _versions(self, user, line, command):
        stores = self.site.stores
        if command in ("undo", "redo"):
            root = stores.step(user, -1 if command == "undo" else +1)
            if root is None:
                return Result(line, err=f"odag: nothing to {command}\n", code=1)
            return Result(line, err=f"odag: {'undid' if command == 'undo' else 'redid'} "
                                    f"to {root[:12]}\n")
        versions, status = stores.history(user)
        if command == "status":
            return Result(line, out=(f"versions  {status['history']}\n"
                                     f"undoable  {status['undoable']}\n"
                                     f"redoable  {status['redoable']}\n"))
        lines = [f"{'*' if v.current else ' '} {v.root[:12]}  {(v.at or '')[:19].replace('T', ' ')}"
                 f"  {v.message or ''}" for v in versions[:30]]
        return Result(line, out="\n".join(lines) + "\n")


def commands():
    """Every OntoDAG command: what it does, and whether it runs here."""
    sub = next(a for a in PARSER._actions if getattr(a, "choices", None))
    described = {a.dest: a.help for a in sub._choices_actions}
    listed = {n for _, group in GROUPS for n in group}
    groups = []
    for title, members in GROUPS + (("Other", tuple(sorted(set(sub.choices) - listed))),):
        rows = []
        for name in members:
            if name not in sub.choices:
                continue
            touched = COMMAND_EFFECTS.get(name, frozenset({"unknown"}))
            if name in VOCABULARY:
                where = "anyone, to look (list, --show, --diff)"
            elif touched <= {"reads"}:
                where = "anyone"
            elif touched <= ON_A_STORE:
                where = "your store"
            else:
                where = None
            rows.append({"name": name, "help": described.get(name, ""), "where": where,
                         "why": None if where else REFUSED.get(
                             name, "touches the server's " + ", ".join(sorted(touched - ON_A_STORE)))})
        if rows:
            groups.append((title, rows))
    return groups
