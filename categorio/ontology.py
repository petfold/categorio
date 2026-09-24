"""OntoDAG plumbing: the public store, pack descriptions, `.od` text.

The public store is every shipped pack merged into one OntoDAG, the shared
vocabulary (DESIGN §2). It is built in memory at startup rather than read
from a file: merging the packs takes about three seconds, parsing the same
graph from `.od` text more than twice that.
"""

import os
import tempfile
import threading
from collections import OrderedDict

from ontodag import packs as _packs
from ontodag.dag import OntoDAG
# The native reader/writer are path-based and private to the CLI module; going
# through a temporary file keeps this site on exactly the CLI's format rather
# than on a copy of it that could drift.
from ontodag.__main__ import _load_native, _save_native

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
_packs_built = {}
_public = None


def pack_dag(name):
    """One pack on its own, for its entry page and its download."""
    if name not in _packs.PACKS:
        raise KeyError(name)
    with _lock:
        if name not in _packs_built:
            _packs_built[name] = _packs.pack_dag(name)
        return _packs_built[name]


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


def warm():
    public()
    for name in pack_names():
        pack_dag(name)


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
    fd, path = tempfile.mkstemp(suffix=".od")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            return _load_native(path)
        except ValueError:
            raise
        except Exception as exc:          # shlex errors, bad edges, cycles
            raise ValueError(f"not a readable .od file ({exc})") from exc
    finally:
        os.unlink(path)


def serialize(dag):
    """OntoDAG -> canonical `.od` text."""
    fd, path = tempfile.mkstemp(suffix=".od")
    os.close(fd)
    try:
        _save_native(dag, path)
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def parents(dag, name):
    """Live parents, without the root."""
    node = dag.nodes[name]
    return sorted(p.name for p in node.parents
                  if dag.nodes.get(p.name) is p and p.name not in (name, ROOT))


def children(dag, name):
    return sorted(n.name for n in dag.nodes[name].neighbors)


def cone(dag, name, skip=frozenset()):
    """Everything below `name` in `dag`, never entering a node in `skip`."""
    if name not in dag.nodes:
        return set()
    seen, stack = set(), [dag.nodes[name]]
    while stack:
        for child in stack.pop().neighbors:
            if child.name not in seen and child.name not in skip:
                seen.add(child.name)
                stack.append(child)
    return seen
