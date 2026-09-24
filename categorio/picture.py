"""Pictures of one category and its neighbours, as inline SVG.

Drawn the way OntoDAG's own visualiser draws (Graphviz `dot`, top to bottom,
synthetic node ids so any name renders), but from a viewer's *view* rather
than from a store: a store's picture would show edges the viewer may not see
(a shared category's private parents, other members of a group). What is
drawn here is exactly what the page's lists show, so the two cannot
disagree about what is visible.

Every node links to its page. Graphviz escapes labels in its SVG output, and
the links are built here, so names are never markup — neither in the page
nor in Graphviz, where a name like `<b>x</b>` would otherwise be read as an
HTML label.
"""

import re
from urllib.parse import quote

from categorio import names

LIMIT = 30
# More children than this and the picture turns sideways, so they stack in a
# readable column instead of one row too wide to read.
SIDEWAYS = 6
_SAFE = "()=,-_.~*+:@"

FILL = {"focus": "#ffd9a0", "own": "#dcefe6", "foreign": "#ebe3f5",
        "public": "#eef2f7", "address": "#ffffff", "more": "#f7f7f7"}


def url(entry):
    if entry["kind"] == "foreign":
        return f"/from/{entry['owner']}/c/{quote(entry['name'], safe=_SAFE)}"
    return f"/c/{quote(entry['name'], safe=_SAFE)}"


def label(entry):
    if entry["kind"] == "address":
        return "@" + names.short(entry["name"])
    if entry["kind"] == "foreign":
        return f"{entry['name']}\n· {entry['owner']}"
    return entry["name"]


def draw(focus, above, below, limit=LIMIT):
    """SVG text: `focus` (an entry) with the entries above and below it."""
    import graphviz

    graph = graphviz.Digraph(format="svg")
    sideways = len(below) > SIDEWAYS
    graph.attr(rankdir="LR" if sideways else "TB", bgcolor="transparent",
               nodesep="0.12" if sideways else "0.25", ranksep="0.6" if sideways else "0.45")
    graph.attr("node", shape="box", style="rounded,filled", color="#b8b2a7",
               fontname="Helvetica", fontsize="11", margin="0.12,0.05")
    graph.attr("edge", color="#9a958b", arrowsize="0.6")

    ids = {}

    def node(entry, fill=None):
        key = (entry["kind"], entry.get("owner"), entry["name"])
        if key not in ids:
            ids[key] = f"n{len(ids)}"
            # nohtml: a name shaped like `<b>…</b>` is text, never a Graphviz HTML label
            graph.node(ids[key], graphviz.nohtml(label(entry)), URL=url(entry), target="_top",
                       tooltip=graphviz.nohtml(entry["name"]),
                       fillcolor=fill or FILL[entry["kind"]])
        return ids[key]

    centre = node(focus, FILL["focus"])
    for entry in above[:limit]:
        graph.edge(node(entry), centre)
    shown = below[:limit]
    for entry in shown:
        graph.edge(centre, node(entry))
    if len(below) > len(shown):
        graph.node("more", f"… {len(below) - len(shown)} more", fillcolor=FILL["more"],
                   style="rounded,filled,dashed")
        graph.edge(centre, "more", style="dashed")

    svg = graph.pipe().decode("utf-8")
    # Inline it: drop the XML prolog, doctype and comments Graphviz writes.
    svg = svg[svg.index("<svg"):]
    return re.sub(r"<!--.*?-->", "", svg, flags=re.S)
