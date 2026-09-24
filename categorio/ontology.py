"""OntoDAG plumbing: the public store, pack descriptions, `.od` text.

The public store is every shipped pack merged into one OntoDAG, the shared
vocabulary (DESIGN §2). It is built in memory at startup rather than read
from a file: merging the packs takes about three seconds, parsing the same
graph from `.od` text more than twice that.
"""

import threading
from collections import OrderedDict

from ontodag import packs as _packs
from ontodag import native as _native
from ontodag.dag import OntoDAG

from categorio.names import ROOT

# Short descriptions of the shipped packs, in the order the site lists them.
PACK_INFO = OrderedDict([
    ("core", "An upper ontology of everyday things in ten branches — objects, "
             "agents, places, events, information — built by consensus over "
             "WordNet, SUMO, OpenCyc, schema.org, Wikidata and others."),
    ("physics", "Forces, fields, particles and the quantities that measure them."),
    ("mathematics", "Structures, numbers, functions and the branches that study them."),
    ("chemistry", "Elements, compounds, reactions and laboratory practice."),
    ("biology", "Organisms, cells, anatomy and the processes of life."),
    ("medicine", "Diseases, symptoms, treatments, drugs and clinical practice."),
    ("ai", "Models, learning methods, agents and the vocabulary of machine intelligence."),
    ("economics", "Markets, money, assets, firms and financial instruments."),
    ("computing", "Hardware, software, networks, languages and data."),
    ("geography", "Continents, countries, landforms and bodies of water."),
    ("space", "Stars, planets, spacecraft and the rest of the sky."),
    ("prelude", "The everyday dimensions: time, weight, length and the like — "
                "categories that carry typed, ordered values."),
    ("crypto-core", "Units for BTC, ETH, BZZ and DAI, with their protocol denominations."),
    ("crypto-majors", "Units for the market's major coins."),
    ("stablecoins", "Units for the common stablecoins."),
    ("fiat-iso4217", "Units for about 150 national currencies (ISO 4217)."),
])
UNIT_PACKS = ("prelude", "crypto-core", "crypto-majors", "stablecoins", "fiat-iso4217")


def pack_names():
    known = [n for n in PACK_INFO if n in _packs.PACKS]
    return known + sorted(n for n in _packs.PACKS if n not in PACK_INFO)


def pack_summary(name):
    version, _entries = _packs.PACKS[name]
    count, _space, noun = _packs.describe(name).partition(" ")
    return {"name": name, "version": version, "size": f"{int(count):,} {noun}",
            "about": PACK_INFO.get(name, ""), "units": name in UNIT_PACKS}


_lock = threading.Lock()
_public = None


def pack_dag(name):
    """One pack on its own, as OntoDAG builds it: for a download. Built on
    request and not kept — the site holds one copy of the vocabulary, the
    public store, and everything else reads that."""
    if name not in _packs.PACKS:
        raise KeyError(name)
    return _packs.pack_dag(name)


# A pack's names and its top come from OntoDAG (0.27), read from the pack's
# entry list: no pack DAG is built for them.
pack_members = _packs.pack_members
pack_top = _packs.pack_top


def packs_used(dag):
    """The packs a store uses at least one name of, in listing order."""
    present = set(dag.nodes)
    return [n for n in pack_names() if n != "prelude" and pack_members(n) & present]


def with_packs(dag, chosen):
    """A copy of `dag` with the whole of each chosen pack merged in, as
    `odag pack NAME` would do — for an export, built when asked for."""
    copy = dag.deepcopy()
    for name in chosen:
        _packs.apply(copy, name)
    return copy


def public():
    """The public store: every pack, merged. Built once per process."""
    global _public
    if _public is None:
        with _lock:
            if _public is None:
                dag = OntoDAG()
                for name in pack_names():
                    _packs.apply(dag, name)
                _public = dag
    return _public


def reset_public():
    """Throw the public store away, to be rebuilt on next use."""
    global _public
    with _lock:
        _public = None


def warm():
    public()


def is_public(name):
    return name != ROOT and name in public().nodes


def context(names):
    """The public ancestors of `names`, as a small DAG to merge into a store.

    A store keeps the chain its public categories hang from, the way `odag
    excerpt --context` does, so that its own queries (`get animal` finding
    `rex ⊑ dog`) and its exported file work without the whole vocabulary."""
    pub = public()
    wanted = set()
    for name in names:
        if is_public(name):
            wanted.add(name)
            wanted.update(a.name for a in pub.get_ancestors(name) if a.name != ROOT)
    return pub.induced_subdag(wanted) if wanted else None


def prelude():
    dag = OntoDAG()
    _packs.apply(dag, "prelude")
    return dag


# ---- .od text ----------------------------------------------------------------

def parse(text):
    """`.od` text -> OntoDAG. Raises ValueError on a malformed file."""
    try:
        return _native.loads(text, source="the file")
    except ValueError:
        raise
    except Exception as exc:          # shlex errors, bad edges, cycles
        raise ValueError(f"not a readable .od file ({exc})") from exc


def serialize(dag):
    """OntoDAG -> canonical `.od` text, as `odag` writes it."""
    return _native.dumps(dag)


def parents(dag, name):
    """Live parents, without the root."""
    node = dag.nodes[name]
    return sorted(p.name for p in node.parents
                  if dag.nodes.get(p.name) is p and p.name not in (name, ROOT))


def children(dag, name):
    return sorted(n.name for n in dag.nodes[name].neighbors)
