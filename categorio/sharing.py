"""The seeing rule (DESIGN §4) and receiving (§6).

    You see node x of O's store if x is below one of your addresses in O's
    store, and O's address is filed in your store (not under `blocked`).

The first half is OntoDAG's own rule now (`ontodag.sharing`, 0.28 —
docs/plans/SHARING.md there): reach, where shares land, and what an edit
takes away. What stays here is this site's policy on top of it: whose
addresses are whose, acceptance and blocking, requests and their settings,
and the §10 exclusion of what was filed before an address was registered
(passed to OntoDAG as `exclude`).

Everything here reads stores; nothing writes.
"""

import threading
from collections import OrderedDict

from ontodag import sharing as _rule

from categorio import names, ontology


class Shared:
    """What one store shares with one reader."""

    __slots__ = ("sender", "items", "landing")

    def __init__(self, sender, items, landing):
        self.sender = sender
        self.items = items        # every shared node name (addresses excluded)
        self.landing = landing    # reader's address -> names filed directly under it

    def __bool__(self):
        return bool(self.items)

    def __len__(self):
        return len(self.items)


def _is_content(name):
    return not names.is_address(name) and name not in names.SETTINGS


class Sharing:
    def __init__(self, stores):
        self.stores = stores
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    # ---- whose addresses -----------------------------------------------------

    def addresses(self, user):
        """The reader's registered addresses: the account's own, and every
        address tied to one of its categories that is in its store now."""
        own = self.stores.get(user)
        rows = self.stores.db.query("SELECT address FROM addresses WHERE owner = ?", (user,))
        base = names.address(user)
        return tuple([base] + sorted(r["address"] for r in rows
                                     if r["address"] != base and r["address"] in own.nodes))

    # ---- the rule --------------------------------------------------------------

    def shared(self, sender, reader):
        """What `sender`'s store has below `reader`'s addresses, less what
        was already there when each address was registered."""
        if sender == reader:
            return Shared(sender, frozenset(), {})
        addresses = self.addresses(reader)
        key = (sender, self.stores.revision(sender), addresses)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        dag = self.stores.get(sender)
        # What was below an address before it was registered never counts
        # (§10), and settings are never content: neither is entered.
        exclude = {a: self.stores.preexisting(a, sender) | names.SETTINGS
                   for a in addresses}
        items = {n for n in _rule.reach(dag, addresses, exclude) if _is_content(n)}
        landing = {a: direct for a, names_ in _rule.landing(dag, addresses, exclude).items()
                   if (direct := [n for n in names_ if _is_content(n)])}
        result = Shared(sender, frozenset(items), landing)
        with self._lock:
            self._cache[key] = result
            while len(self._cache) > 512:
                self._cache.popitem(last=False)
        return result

    def blocked(self, reader, sender):
        own = self.stores.get(reader)
        address = names.address(sender)
        return (address in own.nodes and names.BLOCKED in own.nodes
                and own.is_below(address, names.BLOCKED))

    def accepted(self, reader, sender):
        """The second half of the rule: the sender is filed in your store."""
        return names.address(sender) in self.stores.get(reader).nodes \
            and not self.blocked(reader, sender)

    def senders(self, reader):
        """Every other store that mentions one of the reader's addresses and
        actually shares something through it."""
        found = set()
        for address in self.addresses(reader):
            found.update(self.stores.mentioning(address))
        found.discard(reader)
        return sorted(s for s in found if self.shared(s, reader))

    def visible(self, reader):
        """{sender: Shared} for every accepted sender — what the reader sees."""
        return {s: self.shared(s, reader) for s in self.senders(reader)
                if self.accepted(reader, s)}

    # ---- requests (§6) -------------------------------------------------------

    def shows_requests(self, reader, address):
        """The nearest setting wins: the address's own, then the account's,
        then the default, which is show."""
        own = self.stores.get(reader)
        for where in (address, names.address(reader)):
            if where not in own.nodes:
                continue
            below = set(ontology.children(own, where))
            if names.HIDE_REQUESTS in below:
                return False
            if names.SHOW_REQUESTS in below:
                return True
        return True

    def setting(self, reader, address):
        """'show', 'hide', or None when the address has no setting of its own."""
        own = self.stores.get(reader)
        if address not in own.nodes:
            return None
        below = set(ontology.children(own, address))
        if names.HIDE_REQUESTS in below:
            return "hide"
        if names.SHOW_REQUESTS in below:
            return "show"
        return None

    def requests(self, reader):
        """Senders who share with you and are neither accepted nor blocked,
        where the address they used shows requests. Names and counts only."""
        out = []
        for sender in self.senders(reader):
            if self.accepted(reader, sender) or self.blocked(reader, sender):
                continue
            shared = self.shared(sender, reader)
            via = [a for a in shared.landing if self.shows_requests(reader, a)]
            if via:
                out.append({"sender": sender, "count": len(shared), "via": via})
        return out

    # ---- what an edit would take away (§9) -----------------------------------

    @staticmethod
    def losses(before, after, owner):
        """{address: names it would stop seeing} between two states of
        `owner`'s store, for every other account's address in it."""
        others = [n for n in before.nodes
                  if names.parse_address(n) and names.owner_of(n) != owner]
        lost = _rule.losses(before, after, others, exclude=names.SETTINGS)
        return {a: gone for a, all_ in lost.items()
                if (gone := [n for n in all_ if _is_content(n)])}
