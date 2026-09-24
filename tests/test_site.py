"""The site, end to end, against docs/DESIGN.md."""

import io
import re

import pytest

from categorio import create_app, names, ontology

D = names.DOMAIN


@pytest.fixture()
def app(tmp_path):
    return create_app({"DATA": str(tmp_path), "TESTING": True, "SECRET_KEY": "test"})


class Browser:
    """One person's session."""

    def __init__(self, app):
        self.client = app.test_client()

    def get(self, path):
        return self.client.get(path)

    def text(self, path):
        return self.client.get(path).get_data(as_text=True)

    def csrf(self):
        page = self.text("/login")
        return re.search(r'name="csrf" value="([^"]+)"', page).group(1)

    def post(self, path, data=None, follow=True, **kw):
        data = dict(data or {})
        data["csrf"] = self.csrf()
        return self.client.post(path, data=data, follow_redirects=follow, **kw)

    def say(self, path, data=None, **kw):
        return self.post(path, data, **kw).get_data(as_text=True)

    def register(self, name, password="correct horse"):
        return self.post("/register", {"username": name, "password": password})

    def put(self, name, parents=""):
        return self.say("/put", {"name": name, "parents": parents})

    def share(self, name, who):
        return self.say("/share", {"name": name, "address": who})


@pytest.fixture()
def people(app):
    def make(*who):
        out = []
        for name in who:
            b = Browser(app)
            b.register(name)
            out.append(b)
        return out
    return make


def acme_setup(acme):
    """DESIGN §5, built through the site."""
    for n, p in [("employees", ""), ("sales", ""), ("merger-plans", ""),
                 ("employee-information", "employees, merger-plans"),
                 ("handbook", "employee-information, document"),
                 ("sales-leads", "sales"), ("employees", "sales")]:
        acme.put(n, p)
    for who in ("ada", "bob", "harry"):
        acme.share("employees", who)
    acme.share("sales", "harry")


def flash(page):
    return " ".join(re.findall(r'<p class="flash"[^>]*>(.*?)</p>', page))


# ---- the public store --------------------------------------------------------

def test_visitors_browse_the_public_store(app):
    b = Browser(app)
    assert "/packs/core" in b.text("/")
    assert "physical-object" in b.text("/packs/core")
    page = b.text("/c/artifact")
    assert "device" in page and "under" in page
    assert "Narrow by" in b.text("/q?t=artifact&t=container")
    assert "toaster" in b.text("/search?q=toast")
    assert b.get("/c/no-such-thing").status_code == 404


def test_names_with_slashes(app):
    assert "unit-declaration" in Browser(app).text("/c/unit(sat=1/100000000BTC)")


def test_pack_download_round_trips(app):
    body = Browser(app).text("/packs/physics/download")
    assert body.startswith("# ontodag store v1")
    assert len(ontology.parse(body).nodes) == len(ontology.pack_dag("physics").nodes)


def test_setting_names_are_not_vocabulary():
    assert not names.SETTINGS & set(ontology.public().nodes)


# ---- accounts ----------------------------------------------------------------

def test_register_login_logout(app):
    b = Browser(app)
    b.register("ada")
    assert f"ada@{D}" in b.text("/")
    b.post("/logout")
    assert "Create an account" in b.text("/")
    assert "Wrong username" in b.say("/login", {"username": "ada", "password": "nope-nope"})
    b.post("/login", {"username": "ADA", "password": "correct horse"})
    assert f"ada@{D}" in b.text("/")


def test_names_are_taken_once(app, people):
    people("ada")
    assert "taken" in Browser(app).register("ada").get_data(as_text=True)


def test_csrf(app, people):
    (ada,) = people("ada")
    assert ada.client.post("/put", data={"name": "x"}).status_code == 400


# ---- your own store ----------------------------------------------------------

def test_classifying_is_private(app, people):
    ada, bob = people("ada", "bob")
    ada.put("rex", "dog")
    assert "rex" in ada.text("/q?t=animal")          # the public chain came along
    assert "rex" in ada.text("/c/dog")
    assert "rex" not in bob.text("/c/dog")
    assert "rex" not in Browser(app).text("/c/dog")
    assert bob.get("/c/rex").status_code == 404
    assert "/c/rex" not in bob.text("/search?q=rex")


def test_own_categories_and_edits(app, people):
    (ada,) = people("ada")
    for n, p in [("travel", ""), ("japan", "travel"), ("flight", ""), ("jal123", "japan, flight")]:
        ada.put(n, p)
    assert "jal123" in ada.text("/q?t=travel")
    assert "no category called nowhere" in ada.put("x", "nowhere")
    assert "cycle" in ada.put("travel", "jal123")
    ada.say("/unfile", {"name": "jal123", "parent": "flight"})
    assert "jal123" not in ada.text("/q?t=flight")
    ada.say("/remove", {"name": "japan"})
    assert "jal123" in ada.text("/c/travel")
    assert "setting name" in ada.put("blocked")
    assert "address" in ada.put("x@y")


def test_undo_redo(app, people):
    (ada,) = people("ada")
    ada.put("travel")
    assert "/c/travel" in ada.text("/")
    ada.say("/store/undo")
    assert "/c/travel" not in ada.text("/")
    ada.say("/store/redo")
    assert "/c/travel" in ada.text("/")
    assert "put travel" in ada.text("/store")


# ---- sharing (DESIGN §4-§6) --------------------------------------------------

def test_acme(app, people):
    acme, ada, bob, harry = people("acme", "ada", "bob", "harry")
    acme_setup(acme)

    # before accepting: a request with a count, no content
    home = ada.text("/")
    assert "acme</strong> wants to share" in home
    assert "handbook" not in home
    assert ada.get("/from/acme/c/handbook").status_code == 404

    ada.say("/accept", {"sender": f"acme@{D}", "under": ""})
    assert "/from/acme/c/employees" in ada.text(f"/c/acme@{D}")
    page = ada.text("/from/acme/c/employee-information")
    assert "handbook" in page
    assert "merger-plans" not in page                  # a private parent stays hidden
    assert ada.get("/from/acme/c/merger-plans").status_code == 404
    assert ada.get("/from/acme/c/sales-leads").status_code == 404
    assert "bob" not in ada.text("/from/acme/c/employees")   # members don't see each other

    # the shared handbook sits under the public `document` in ada's view only
    assert "/from/acme/c/handbook" in ada.text("/c/document")
    assert "/from/acme/c/handbook" not in bob.text("/c/document")   # bob hasn't accepted
    assert "/from/acme/c/handbook" not in Browser(app).text("/c/document")

    harry.say("/accept", {"sender": f"acme@{D}", "under": ""})
    assert harry.get("/from/acme/c/sales-leads").status_code == 200
    assert harry.get("/from/acme/c/handbook").status_code == 200   # sales has all employees have
    assert "/from/acme/c/handbook" in harry.text("/q?t=document")


def test_block(app, people):
    acme, ada = people("acme", "ada")
    acme_setup(acme)
    ada.say("/block", {"sender": f"acme@{D}"})
    assert "wants to share" not in ada.text("/")
    assert ada.get("/from/acme/c/handbook").status_code == 404
    ada.say("/unblock", {"sender": f"acme@{D}"})
    assert ada.get("/from/acme/c/handbook").status_code == 200   # still in the store: accepted


def test_sharing_with_someone_accepts_them(app, people):
    ada, bob = people("ada", "bob")
    bob.put("notes")
    bob.share("notes", "ada")
    ada.put("reply")
    ada.share("reply", "bob")
    assert bob.get("/from/ada/c/reply").status_code == 200
    assert ada.get("/from/bob/c/notes").status_code == 200


def test_addresses_tied_to_categories(app, people):
    acme, ada, eve = people("acme", "ada", "eve")
    ada.put("work")
    ada.say("/address/new", {"tag": "work", "under": "work"})
    ada.say("/address/setting", {"address": f"ada+work@{D}", "value": "hide"})
    ada.say("/accept", {"sender": f"acme@{D}", "under": "work"})

    acme.put("q3-roster")
    acme.share("q3-roster", "ada+work")
    eve.put("spam")
    eve.share("spam", "ada+work")

    assert "eve</strong>" not in ada.text("/")                      # hidden here: no request
    assert "/from/acme/c/q3-roster" in ada.text(f"/c/ada+work@{D}")    # arrives at the address
    assert f"/c/ada+work@{D}" in ada.text("/c/work")                # which is in work

    # the account-wide default still shows requests at the base address
    eve.share("spam", "ada")
    assert "eve</strong> wants to share" in ada.text("/")


def test_unregistered_addresses_never_receive(app, people):
    """DESIGN §10: a share to an address that doesn't exist yet never counts,
    even after the name is registered — and the sender can't tell."""
    carol, frank = people("carol", "frank")
    carol.put("secret")
    carol.put("hello")
    to_unknown = flash(carol.share("secret", "dave"))
    to_known = flash(carol.share("hello", "frank"))
    assert to_unknown.replace("secret", "X").replace("dave", "Y") == \
        to_known.replace("hello", "X").replace("frank", "Y")
    assert "own addresses" in carol.share("hello", "carol")

    (dave,) = people("dave")
    assert "wants to share" not in dave.text("/")
    dave.say("/accept", {"sender": f"carol@{D}", "under": ""})
    assert dave.get("/from/carol/c/secret").status_code == 404
    carol.put("later")
    carol.share("later", "dave")
    assert dave.get("/from/carol/c/later").status_code == 200


def test_losing_access_asks_first(app, people):
    acme, ada = people("acme", "ada")
    acme_setup(acme)
    page = acme.say("/unfile", {"name": "employee-information", "parent": "employees"})
    assert "would no longer see" in page and "handbook" in page
    assert "employee-information employees" in acme.text("/store/export")
    acme.say("/unfile", {"name": "employee-information", "parent": "employees", "confirm": "1"})
    assert "employee-information employees" not in acme.text("/store/export")


# ---- files -------------------------------------------------------------------

def test_export_import(app, people):
    ada, bob = people("ada", "bob")
    ada.put("travel")
    ada.put("rex", "dog")
    body = ada.get("/store/export").get_data(as_text=True)
    assert "rex dog" in body
    assert re.search(r"^dog ", body, re.M)                  # self-contained: dog's chain is in it

    file = f"# ontodag store v1\ntrip\nkyoto trip bob@{D}\n".encode()
    page = ada.say("/store/import", {"file": (io.BytesIO(file), "t.od")},
                   content_type="multipart/form-data")
    assert "This file shares" in page and "kyoto" in page
    token = re.search(r'name="token" value="([^"]+)"', page).group(1)
    ada.say("/store/import/confirm", {"token": token})
    assert "/c/trip" in ada.text("/")
    assert bob.get("/from/ada/c/kyoto").status_code == 404  # bob hasn't accepted ada
    bob.say("/accept", {"sender": f"ada@{D}", "under": ""})
    assert bob.get("/from/ada/c/kyoto").status_code == 200

    bad = ada.say("/store/import", {"file": (io.BytesIO(b"x mallory@example.com\n"), "x.od")},
                  content_type="multipart/form-data")
    assert "not a categor.io address" in bad


def test_shares_through_groups_are_shown(app, people):
    """OntoDAG drops `employees ⊑ harry` as implied by `employees ⊑ sales ⊑
    harry`; the owner must still see that harry has it."""
    acme, harry = people("acme", "harry")
    acme_setup(acme)
    page = acme.text("/c/employees")
    assert "through a group" in page and f"/c/harry@{D}" in page
    assert f"/c/harry@{D}" in acme.text("/c/handbook")


def test_your_things_come_first(app, people):
    (ada,) = people("ada")
    ada.put("work")                                  # a public word: the activity
    ada.put("payslips", "work")
    page = ada.text("/c/work")
    assert "/c/payslips" in page
    assert "/c/census" not in page                   # the vocabulary under work is folded
    assert "public categories under work" in page
    assert "activity ×" not in page                  # not an edge ada made
    assert "home ×" in page


def test_dimension_values(app, people):
    (ada,) = people("ada")
    ada.put("tokyo-trip", "time(2026-08)")
    assert "/c/tokyo-trip" in ada.text("/q?t=time(2026)")          # computed, no edge stored
    assert "/c/tokyo-trip" not in ada.text("/q?t=time(2025)")
    assert "time(" in ada.put("x", "time(not-a-date)")               # OntoDAG's own message
    export = ada.text("/store/export")
    assert ontology.parse(export).get(["time(2026)"])


def test_home_link_everywhere(app, people):
    (ada,) = people("ada")
    for b in (Browser(app), ada):
        for path in ("/", "/c/artifact", "/packs/core", "/search?q=dog"):
            assert '<a href="/"' in b.text(path)
    assert 'href="/" aria-current="page">Home' in ada.text("/")
    assert 'aria-current="page">Store' in ada.text("/store")


def test_guide(app, people):
    (ada,) = people("ada")
    for b in (Browser(app), ada):
        assert 'href="/guide"' in b.text("/c/artifact")
        page = b.text("/guide")
        assert "<h1" in page and "Part 1: Exploring" in page
    # the contents links resolve to headings on the page
    page = Browser(app).text("/guide")
    for anchor in re.findall(r'href="#([^"]+)"', page):
        assert f'id="{anchor}"' in page, anchor
