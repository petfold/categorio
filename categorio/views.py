"""What one viewer sees: their store, the public store, and what is shared
with them — combined per page, never merged into one graph (DESIGN §2).

A viewer is a username, or None for a visitor who is not signed in (who sees
the public store only). Entries are plain dicts the templates render:

    {"kind": "public" | "own" | "address" | "foreign",
     "name", "owner" (foreign only), "has_children", "count" (public only)}
"""

from ontodag.sharing import reach

from categorio import names, ontology


def _entry_public(name):
    node = ontology.public().nodes[name]
    return {"kind": "public", "name": name, "has_children": bool(node.neighbors),
            "count": node.descendant_count}


def _entry_own(dag, name):
    kind = "address" if names.is_address(name) else (
        "public" if ontology.is_public(name) else "own")
    if kind == "public":
        return _entry_public(name)
    return {"kind": kind, "name": name, "has_children": bool(dag.nodes[name].neighbors)}


def _entry_foreign(dag, owner, name, items):
    if ontology.is_public(name):
        return _entry_public(name)
    node = dag.nodes[name]
    return {"kind": "foreign", "name": name, "owner": owner,
            "has_children": any(c.name in items for c in node.neighbors)}


def _sorted(entries):
    unique = {}
    for e in entries:
        unique.setdefault((e["kind"], e.get("owner"), e["name"]), e)
    order = {"address": 0, "own": 1, "foreign": 2, "public": 3}
    return sorted(unique.values(),
                  key=lambda e: (order[e["kind"]], not e["has_children"], e["name"].lower()))


class View:
    def __init__(self, site, user):
        self.site = site
        self.user = user
        self.own = site.stores.get(user) if user else None
        self.visible = site.sharing.visible(user) if user else {}
        self.addresses = site.sharing.addresses(user) if user else ()

    # ---- one node ------------------------------------------------------------

    def node(self, name):
        """A public name, a category of the viewer's own, or an address in
        the viewer's store. None if the viewer has no such node."""
        pub = ontology.public()
        in_pub = ontology.is_public(name)
        in_own = self.own is not None and name in self.own.nodes and name != names.ROOT
        if names.is_address(name) and not in_own:
            return None
        if name in names.SETTINGS or not (in_pub or in_own):
            return None

        above, shared_with, own_above, below, through = [], [], [], [], []
        at_home = False
        public_above, public_below = [], []
        if in_pub:
            public_above = ontology.parents(pub, name)
            public_below = ontology.children(pub, name)
            above += [_entry_public(p) for p in public_above]
        if in_own:
            for p in ontology.parents(self.own, name):
                if p == names.address(self.user):
                    at_home = True
                elif names.owner_of(p) == self.user:
                    continue                                   # one of my own addresses
                elif names.is_address(p):
                    shared_with.append(p)
                elif p in names.SETTINGS:
                    continue
                else:
                    above.append(_entry_own(self.own, p))
                    if p not in public_above:          # an edge you made, not the vocabulary's
                        own_above.append(p)
            below += [_entry_own(self.own, c) for c in ontology.children(self.own, name)
                      if c not in names.SETTINGS and c not in public_below]
            # addresses this reaches through a group: OntoDAG keeps only the
            # reduction, so these have no edge of their own here
            through = sorted(a.name for a in self.own.get_ancestors(name)
                             if names.is_address(a.name) and names.owner_of(a.name) != self.user
                             and a.name not in shared_with)

        # what others share lands here
        for sender, shared in self.visible.items():
            dag = self.site.stores.get(sender)
            if in_pub and name in dag.nodes:
                below += [_entry_foreign(dag, sender, c, shared.items)
                          for c in ontology.children(dag, name) if c in shared.items]
            if name in shared.landing:                         # one of my addresses
                below += [_entry_foreign(dag, sender, c, shared.items)
                          for c in shared.landing[name]]
            if name == names.address(sender):                  # the sender's own entry
                for listed in shared.landing.values():
                    below += [_entry_foreign(dag, sender, c, shared.items) for c in listed]

        # In your own categories, your things come first; the public
        # vocabulary below them is one click away. Elsewhere it is the page.
        public_entries = [_entry_public(c) for c in public_below]
        folded = in_own and bool(below)
        if not folded:
            below += public_entries
        view = {
            "name": name,
            "public_below": len(public_entries) if folded else 0,
            "through": through if in_own else [],
            "kind": "address" if names.is_address(name) else ("public" if in_pub else "own"),
            "above": _sorted(above),
            "below": _sorted(below),
            "shared_with": sorted(shared_with),
            "own_above": sorted(own_above),
            "at_home": at_home,
            "count": pub.nodes[name].descendant_count if in_pub else None,
            "mine": in_own,
        }
        if view["kind"] == "address":
            view.update(self._address(name))
        return view

    def _address(self, name):
        """Extra facts about an address node in the viewer's store."""
        user = names.owner_of(name)
        own = self.own
        placed = [p for p in ontology.parents(own, name)
                  if not names.is_address(p) and p not in names.SETTINGS]
        facts = {"placed": placed, "short": names.short(name),
                 "yours": user == self.user,
                 "tag": (names.parse_address(name) or (None, None))[1]}
        if facts["yours"]:
            facts["setting"] = self.site.sharing.setting(self.user, name)
            facts["base"] = name == names.address(self.user)
        else:
            facts["contact"] = user
            facts["blocked"] = user is not None and self.site.sharing.blocked(self.user, user)
            # what the viewer shares with this address: their own names below it
            facts["sharing"] = sorted(n for n in reach(own, [name])
                                      if not names.is_address(n) and n not in names.SETTINGS)
        return facts

    def foreign(self, owner, name):
        """A node of another store, if it is shared with the viewer."""
        shared = self.visible.get(owner)
        if shared is None or name not in shared.items:
            return None
        dag = self.site.stores.get(owner)
        above, landed = [], []
        for p in ontology.parents(dag, name):
            if p in self.addresses:
                landed.append(p)
            elif p in shared.items:
                above.append(_entry_foreign(dag, owner, p, shared.items))
            elif ontology.is_public(p):
                above.append(_entry_public(p))
        below = [_entry_foreign(dag, owner, c, shared.items)
                 for c in ontology.children(dag, name) if c in shared.items]
        return {"name": name, "owner": owner, "kind": "foreign",
                "above": _sorted(above), "below": _sorted(below), "landed": landed}

    # ---- queries -------------------------------------------------------------

    def query(self, terms, limit=300):
        """Everything below all of `terms`, from every source the viewer
        can read, and the categories that would narrow it."""
        pub = ontology.public()
        found = {}
        ancestors = {}

        def add(entry, parents):
            key = (entry["kind"], entry.get("owner"), entry["name"])
            found.setdefault(key, entry)
            ancestors.setdefault(key, set()).update(parents)

        for item in pub.get(terms):
            add(_entry_public(item.name), (a.name for a in pub.get_ancestors(item.name)))
        if self.own is not None:
            for item in self.own.get(terms):
                if names.is_address(item.name) or item.name in names.SETTINGS:
                    continue
                add(_entry_own(self.own, item.name),
                    (a.name for a in self.own.get_ancestors(item.name)
                     if not names.is_address(a.name)))
        for sender, shared in self.visible.items():
            dag = self.site.stores.get(sender)
            if not all(t in dag.nodes for t in terms):
                continue
            for item in dag.get(terms):
                if item.name in shared.items:
                    add(_entry_foreign(dag, sender, item.name, shared.items),
                        (a.name for a in dag.get_ancestors(item.name)
                         if a.name in shared.items or ontology.is_public(a.name)))

        entries = _sorted(found.values())
        total = len(entries)
        # a refinement is any readable name held by some of the answer, not all
        counts = {}
        skip = set(terms) | {names.ROOT}
        for key, parents in ancestors.items():
            for p in parents - skip:
                if names.is_address(p) or p in names.SETTINGS:
                    continue
                if ontology.is_public(p) or (self.own is not None and p in self.own.nodes):
                    counts[p] = counts.get(p, 0) + 1
        refine = sorted(((n, c) for n, c in counts.items() if c < total),
                        key=lambda pair: (-pair[1], pair[0]))[:40]
        return {"terms": terms, "entries": entries[:limit], "count": total,
                "more": max(0, total - limit), "refine": refine}

    def search(self, text, limit=60):
        needle = text.strip().lower()
        if not needle:
            return []
        hits = []

        def match(name):
            return needle in name.lower()

        for name in ontology.public().nodes:
            if name != names.ROOT and match(name):
                hits.append(_entry_public(name))
        if self.own is not None:
            for name in self.own.nodes:
                if (name != names.ROOT and match(name) and not ontology.is_public(name)
                        and name not in names.SETTINGS):
                    hits.append(_entry_own(self.own, name))
        for sender, shared in self.visible.items():
            dag = self.site.stores.get(sender)
            hits += [_entry_foreign(dag, sender, n, shared.items)
                     for n in shared.items if match(n) and not ontology.is_public(n)]
        hits.sort(key=lambda e: (not e["name"].lower().startswith(needle),
                                 len(e["name"]), e["name"]))
        return hits[:limit]

    def completions(self, text, limit=12):
        """Names the viewer may file under: their own and public ones."""
        return [e["name"] for e in self.search(text, limit * 3)
                if e["kind"] != "foreign"][:limit]

    # ---- home ------------------------------------------------------------------

    def home(self):
        own = self.own
        base = names.address(self.user)
        mine, addresses, contacts = [], [], []
        # your home: what you filed at the top (under your own address), and
        # your own categories that hang only from the public vocabulary
        for name in ontology.children(own, base):
            if not names.is_address(name) and name not in names.SETTINGS:
                mine.append(dict(_entry_own(own, name), count=None))
        for name in own.nodes:
            if name in (names.ROOT,) or name in names.SETTINGS:
                continue
            if names.is_address(name):
                if names.owner_of(name) == self.user:
                    if name != names.address(self.user):
                        addresses.append(name)
                else:
                    contacts.append(name)
                continue
            if ontology.is_public(name):
                continue
            parents = ontology.parents(own, name)
            if not any(p != base and (not names.is_address(p)) and p not in names.SETTINGS
                       and (not ontology.is_public(p) or base in ontology.parents(own, p))
                       for p in parents):
                mine.append(_entry_own(own, name))
        shared = [{"sender": s, "count": len(sh)} for s, sh in sorted(self.visible.items())]
        return {"mine": _sorted(mine), "addresses": sorted(addresses),
                "categories": sorted(n for n in own.nodes if n != names.ROOT
                                     and not names.is_address(n) and n not in names.SETTINGS
                                     and (not ontology.is_public(n) or base in ontology.parents(own, n))),
                "contacts": sorted(contacts), "shared": shared,
                "requests": self.site.sharing.requests(self.user),
                "setting": self.site.sharing.setting(self.user, names.address(self.user)),
                "base": names.address(self.user)}
