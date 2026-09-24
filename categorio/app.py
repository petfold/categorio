"""categor.io — the public vocabulary for everyone; for each account, a store
of its own, and sharing by filing (docs/DESIGN.md)."""

import os
import secrets
import threading
from functools import wraps
from urllib.parse import quote

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from ontodag import dimensions
from werkzeug.security import check_password_hash, generate_password_hash

from categorio import names, ontology
from categorio.db import Database, now
from categorio.sharing import Sharing
from categorio.stores import Stores
from categorio.views import View

MAX_CATEGORIES = 100_000


class Site:
    """The site's state: login records, the stores, the sharing rule."""

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.db = Database(os.path.join(directory, "logins.sqlite"))
        self.stores = Stores(os.path.join(directory, "stores"), self.db)
        self.sharing = Sharing(self.stores)
        self.imports = {}                  # token -> (user, dag), awaiting confirmation


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        DATA=os.environ.get("CATEGORIO_DATA", app.instance_path),
        SECRET_KEY=os.environ.get("CATEGORIO_SECRET_KEY"),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("CATEGORIO_SECURE_COOKIES") == "1",
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"]:
        # Fine for a laptop; a deployment sets CATEGORIO_SECRET_KEY so that
        # sessions survive a restart and are shared between workers.
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    app.extensions["site"] = Site(app.config["DATA"])
    if not app.config.get("TESTING"):
        # Building the public store takes a few seconds; do it before the
        # first visitor asks.
        threading.Thread(target=ontology.warm, daemon=True).start()

    app.jinja_env.filters["seg"] = lambda name: quote(name, safe="()=,-_.~*+:@")
    app.jinja_env.filters["short"] = names.short
    app.jinja_env.globals["DOMAIN"] = names.DOMAIN
    _register(app)
    return app


# ---- helpers -----------------------------------------------------------------

def site():
    from flask import current_app
    return current_app.extensions["site"]


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def node_url(name):
    return "/c/" + quote(name, safe="()=,-_.~*+:@")


def back(default="/"):
    target = request.form.get("back", "")
    if target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect(default)


def own():
    return site().stores.get(g.user)


def in_store(name):
    """A category in the viewer's store — their own, or a public one they
    use. Not the root, an address or a setting."""
    return (name in own().nodes and name != names.ROOT and not names.is_address(name)
            and name not in names.SETTINGS)


def own_category(name):
    """A category only the viewer's store has (not a public name)."""
    return in_store(name) and not ontology.is_public(name)


def dimension_term(name):
    """A value of a dimension the store declares, such as `time(2026-08)`.
    OntoDAG creates it on first use; its own parse trigger is the same
    test: the head is declared under `dimension`."""
    split = dimensions.split_term(name)
    dag = own()
    return (split is not None and split[0] in dag.nodes and "dimension" in dag.nodes
            and dag.is_below(split[0], "dimension"))


def usable(name):
    """A name the viewer may file under or file: in their store, public,
    or a dimension value."""
    return in_store(name) or ontology.is_public(name) or dimension_term(name)


def with_context(dag, used):
    """Bring in the public ancestors of the public names in `used`."""
    extra = ontology.context(used)
    if extra is not None:
        dag.merge(extra)


def edit(change, message, confirm_text=None):
    """Apply a change to the viewer's store — but when it would stop someone
    seeing something, first show who and what, and ask (DESIGN §9).

    Returns a page to show instead, or None when the change was made."""
    stores, user = site().stores, g.user
    if not request.form.get("confirm"):
        trial = own().deepcopy()
        change(trial)
        losses = {a: gone for a, gone in site().sharing.losses(own(), trial).items()
                  if names.owner_of(a) != user}
        if losses:
            return render_template("confirm.html", losses=losses, message=message,
                                   action=request.path, fields=request.form.to_dict(),
                                   confirm_text=confirm_text or "Go ahead")
    stores.edit(user, change, message)
    if len(own().nodes) > MAX_CATEGORIES:
        stores.step(user, -1)
        raise ValueError(f"a store here holds at most {MAX_CATEGORIES:,} categories")
    return None


def split_names(text):
    return [n.strip() for n in text.split(",") if n.strip()]


def check_incoming(dag):
    """An imported file may hold categories, public names and addresses of
    this site — nothing that claims to be of another site."""
    for name in dag.nodes:
        if names.is_address(name) and names.parse_address(name) is None:
            raise ValueError(f"{name!r} is not a {names.DOMAIN} address")


GUIDE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "docs", "USER_GUIDE.md")
_guide_cache = {}


def user_guide():
    """docs/USER_GUIDE.md as HTML, re-rendered when the file changes."""
    import markdown
    from markupsafe import Markup
    try:
        stamp = os.path.getmtime(GUIDE)
    except OSError:
        abort(404)
    if _guide_cache.get("stamp") != stamp:
        with open(GUIDE, encoding="utf-8") as fh:
            text = fh.read()
        _guide_cache.update(stamp=stamp, html=Markup(
            markdown.markdown(text, extensions=["toc", "tables"])))
    return _guide_cache["html"]


def download(text, filename):
    return Response(text, mimetype="text/plain; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename=\"{filename}\""})


# ---- routes ------------------------------------------------------------------

def _register(app):

    @app.before_request
    def load_user():
        g.user = None
        user = session.get("user")
        if user is not None:
            if site().db.one("SELECT 1 FROM logins WHERE username = ?", (user,)):
                g.user = user
            else:
                session.clear()
        if request.method == "POST":
            sent = request.form.get("csrf", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "The form expired. Go back, reload the page and try again.")

    @app.context_processor
    def inject():
        return {"csrf_token": csrf_token, "user": g.user,
                "me": names.address(g.user) if g.user else None}

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("message.html", title="Not found",
                               text="There is nothing here that you can see."), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("message.html", title="Something is off",
                               text=e.description), 400

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("message.html", title="File too large",
                               text="Imports are limited to 8 MB."), 413

    # -- browsing --

    @app.get("/")
    def home():
        packs = [ontology.pack_summary(n) for n in ontology.pack_names()]
        if g.user is None:
            return render_template("welcome.html", packs=packs)
        return render_template("home.html", home=View(site(), g.user).home(), packs=packs)

    @app.get("/packs/<name>")
    def pack(name):
        try:
            dag = ontology.pack_dag(name)
        except KeyError:
            abort(404)
        pub = ontology.public()
        top = [{"kind": "public", "name": n, "has_children": bool(pub.nodes[n].neighbors),
                "count": pub.nodes[n].descendant_count}
               for n in ontology.children(dag, names.ROOT) if n in pub.nodes]
        top.sort(key=lambda e: (not e["has_children"], e["name"]))
        return render_template("pack.html", info=ontology.pack_summary(name), top=top)

    @app.get("/packs/<name>/download")
    def pack_download(name):
        try:
            dag = ontology.pack_dag(name)
        except KeyError:
            abort(404)
        version = ontology.pack_summary(name)["version"]
        return download(ontology.serialize(dag), f"{name}-v{version}.od")

    @app.get("/c/<path:name>")
    def node(name):
        view = View(site(), g.user).node(name)
        if view is None:
            abort(404)
        return render_template("node.html", view=view)

    @app.get("/from/<owner>/c/<path:name>")
    @login_required
    def foreign(owner, name):
        view = View(site(), g.user).foreign(owner, name)
        if view is None:
            abort(404)
        return render_template("foreign.html", view=view)

    @app.get("/q")
    def query():
        terms = request.args.getlist("t")
        if not terms:
            return redirect(url_for("home"))
        return render_template("query.html", view=View(site(), g.user).query(terms))

    @app.get("/search")
    def search():
        text = request.args.get("q", "")
        return render_template("search.html", text=text,
                               hits=View(site(), g.user).search(text))

    @app.get("/guide")
    def guide():
        return render_template("guide.html", body=user_guide())

    @app.get("/names")
    def completions():
        return {"names": View(site(), g.user).completions(request.args.get("q", ""))}

    # -- accounts --

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            error = None
            if not names.USERNAME.match(username):
                error = "Usernames are 3–32 lowercase letters, digits, dots, dashes or underscores."
            elif len(password) < 8:
                error = "Use a password of at least 8 characters."
            elif (site().db.one("SELECT 1 FROM logins WHERE username = ?", (username,))
                  or site().stores.registered(names.address(username))):
                error = "That name is taken."     # now, or once: never reused
            if error is None:
                site().db.write("INSERT INTO logins (username, password, created) VALUES (?, ?, ?)",
                                (username, generate_password_hash(password), now()))
                site().stores.create(username)
                session.clear()
                session["user"] = username
                return redirect(url_for("home"))
            flash(error)
        return render_template("auth.html", mode="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            row = site().db.one("SELECT * FROM logins WHERE username = ?", (username,))
            if row and check_password_hash(row["password"], request.form.get("password", "")):
                session.clear()
                session["user"] = username
                target = request.args.get("next", "")
                return redirect(target if target.startswith("/") and not target.startswith("//")
                                else url_for("home"))
            flash("Wrong username or password.")
        return render_template("auth.html", mode="login")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    # -- your store --

    def act(view):
        """A write: signed in, and a ValueError becomes a message."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                return view(*args, **kwargs)
            except ValueError as exc:
                flash(str(exc))
                return back()
        return login_required(wrapped)

    @app.post("/put")
    @act
    def put():
        name = request.form.get("name", "").strip()
        parents = split_names(request.form.get("parents", ""))
        if not usable(name):
            names.check_category(name)
        bad = [p for p in parents if not usable(p)]
        if bad:
            raise ValueError("no category called " + ", ".join(bad) + " — add it first")
        existed = name in own().nodes
        # With no parent, a category goes on your home: under your own
        # address, in your own store — which shares it with no one.
        home = [names.address(g.user)] if not parents else []

        def change(dag):
            with_context(dag, [name] + parents)
            dag.put(name, parents + home)
        page = edit(change, f"put {name}")
        if page is not None:
            return page
        if existed and parents:
            flash(f"Filed {name} under {', '.join(parents)}.")
        elif not existed and ontology.is_public(name):
            flash(f"“{name}” is a public category; what you file under it stays yours.")
        return redirect(node_url(name))

    @app.post("/unfile")
    @act
    def unfile():
        name, parent = request.form.get("name", ""), request.form.get("parent", "")
        dag = own()
        if name not in dag.nodes or parent not in dag.nodes:
            raise ValueError("no such category")
        return edit(lambda d: d.reclassify([name], to=(), from_=[parent]),
                    f"unfile {name} from {parent}") or back(node_url(name))

    @app.post("/remove")
    @act
    def remove():
        name = request.form.get("name", "")
        if not (own_category(name) or (names.is_address(name) and name in own().nodes
                                       and name != names.address(g.user))):
            raise ValueError("you can remove only your own categories and contacts")
        parents = [p for p in ontology.parents(own(), name) if not names.is_address(p)]
        page = edit(lambda d: d.remove(name), f"remove {name}", confirm_text="Remove")
        if page is not None:
            return page
        flash(f"Removed {names.short(name)}; what was under it now sits under its parents.")
        return redirect(node_url(parents[0]) if parents else url_for("home"))

    @app.post("/share")
    @act
    def share():
        name = request.form.get("name", "")
        address = names.check_address(request.form.get("address", ""))
        if not in_store(name):
            raise ValueError("you can share categories in your store")
        if names.owner_of(address) == g.user:
            raise ValueError("that is one of your own addresses")
        new = address not in own().nodes

        def change(dag):
            if address not in dag.nodes:
                dag.put(address, [])
            dag.put(name, [address])
        edit(change, f"share {name} with {address}")
        # The same words for an existing and an unknown address (DESIGN §10).
        flash(f"Shared {name} with {names.short(address)}."
              + (f" {address} is new in your store — check the spelling." if new else ""))
        return back(node_url(name))

    @app.post("/unshare")
    @act
    def unshare():
        name, address = request.form.get("name", ""), request.form.get("address", "")
        return edit(lambda d: d.reclassify([name], to=(), from_=[address]),
                    f"unshare {name} with {address}",
                    confirm_text="Stop sharing") or back(node_url(name))

    @app.post("/accept")
    @act
    def accept():
        address = names.check_address(request.form.get("sender", ""))
        under = request.form.get("under", "").strip()
        if under and not in_store(under):
            raise ValueError(f"no category of yours called {under}")

        def change(dag):
            if address not in dag.nodes:
                dag.put(address, [])
            if under:
                dag.put(address, [under])
            if names.BLOCKED in dag.nodes and dag.is_below(address, names.BLOCKED):
                dag.reclassify([address], to=(), from_=[names.BLOCKED])
        edit(change, f"accept {address}")
        flash(f"Accepted {names.short(address)}" + (f", filed under {under}." if under else "."))
        return redirect(node_url(address))

    @app.post("/block")
    @act
    def block():
        address = names.check_address(request.form.get("sender", ""))

        def change(dag):
            if names.BLOCKED not in dag.nodes:
                dag.put(names.BLOCKED, [])
            if address not in dag.nodes:
                dag.put(address, [])
            dag.put(address, [names.BLOCKED])
        edit(change, f"block {address}")
        flash(f"Blocked {names.short(address)}: no requests, nothing shown.")
        return back()

    @app.post("/unblock")
    @act
    def unblock():
        address = names.check_address(request.form.get("sender", ""))
        edit(lambda d: d.reclassify([address], to=(), from_=[names.BLOCKED]),
             f"unblock {address}")
        return back(node_url(address))

    @app.post("/address/new")
    @act
    def new_address():
        tag = request.form.get("tag", "").strip().lower()
        under = request.form.get("under", "").strip()
        address = names.check_address(names.address(g.user, tag))
        if not in_store(under):
            raise ValueError("choose one of your categories for the address")
        edit(lambda d: d.put(address, [under]), f"address {address}")
        flash(f"What is shared with {names.short(address)} now arrives in {under}.")
        return redirect(node_url(address))

    @app.post("/address/setting")
    @act
    def address_setting():
        address = request.form.get("address", "")
        value = request.form.get("value", "")
        if names.owner_of(address) != g.user or address not in own().nodes:
            abort(404)
        if value not in ("show", "hide", "default"):
            abort(400)

        def change(dag):
            for setting in (names.SHOW_REQUESTS, names.HIDE_REQUESTS):
                if setting in dag.nodes and address in ontology.parents(dag, setting):
                    dag.reclassify([setting], to=(), from_=[address])
            if value != "default":
                setting = names.SHOW_REQUESTS if value == "show" else names.HIDE_REQUESTS
                if setting not in dag.nodes:
                    dag.put(setting, [])
                dag.put(setting, [address])
        edit(change, f"requests {value} for {address}")
        return back(node_url(address))

    # -- the store as a whole --

    @app.get("/store")
    @login_required
    def store():
        versions, status = site().stores.history(g.user)
        return render_template("store.html", versions=versions[:30], status=status,
                               size=len(own().nodes) - 1)

    @app.get("/store/export")
    @login_required
    def export():
        return download(ontology.serialize(own()), f"{g.user}.od")

    @app.post("/store/import")
    @act
    def import_preview():
        file = request.files.get("file")
        if file is None or not file.filename:
            raise ValueError("choose a .od file to import")
        try:
            text = file.read().decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("that file is not UTF-8 text — export an .od file with odag") from None
        incoming = ontology.parse(text)
        check_incoming(incoming)
        mine = own()
        arriving = sorted(n for n in incoming.nodes
                          if n != names.ROOT and n not in mine.nodes and not names.is_address(n))
        others = [a for a in incoming.nodes
                  if names.parse_address(a) and names.owner_of(a) != g.user]
        shares = {a: sorted(n for n in ontology.cone(incoming, a) if not names.is_address(n))
                  for a in others}
        token = secrets.token_urlsafe(16)
        site().imports[token] = (g.user, incoming)
        return render_template("import.html", token=token, filename=file.filename,
                               new_own=[n for n in arriving if not ontology.is_public(n)],
                               new_public=[n for n in arriving if ontology.is_public(n)],
                               shares={a: s for a, s in shares.items() if s},
                               contacts=sorted(a for a in others if a not in mine.nodes))

    @app.post("/store/import/confirm")
    @act
    def import_confirm():
        user, incoming = site().imports.pop(request.form.get("token", ""), (None, None))
        if user != g.user:
            raise ValueError("that import has expired — choose the file again")

        def change(dag):
            with_context(dag, list(incoming.nodes))
            dag.merge(incoming)
        page = edit(change, "import")
        if page is not None:
            site().imports[request.form["token"]] = (user, incoming)
            return page
        flash("Imported.")
        return redirect(url_for("home"))

    @app.post("/store/undo")
    @act
    def undo():
        root = site().stores.step(g.user, -1)
        flash("Undone." if root else "Nothing to undo.")
        return redirect(url_for("store"))

    @app.post("/store/redo")
    @act
    def redo():
        root = site().stores.step(g.user, +1)
        flash("Redone." if root else "Nothing to redo.")
        return redirect(url_for("store"))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run categor.io locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
