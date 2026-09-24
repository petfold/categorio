# Roadmap

The design is in [docs/DESIGN.md](docs/DESIGN.md).

## Done: rebuilt on the design (2026-09-24)

- [x] One OntoDAG `rs:` store per account, plus the public store built from the packs; SQL for logins
- [x] Views: your store and the public store, plus what others share with you (§4 rule), with parents filtered
- [x] Sharing: file under an address; groups, nested groups; shares through groups shown to the owner
- [x] Receiving: accept (file the sender), requests, block; addresses tied to categories (`ada+work`) with per-address request settings
- [x] Access-change preview before unfile, move or remove (DESIGN §9)
- [x] Per-account history and undo
- [x] Export and import of your store as a self-contained `.od`, with an import preview
- [x] Anonymous browsing of the public store
- [x] Unknown addresses refused silently; shares from before registration ignored; addresses never reused (DESIGN §10)

- [x] Pictures (Graphviz, from the viewer's view) and a console for the safe subset of `odag` (DESIGN §12)

- [x] Memory: one shared public vocabulary, no per-pack copies, a cap on user stores in memory; whole packs go into exports, not stores (DESIGN §2, §8)

- [x] The sharing rule taken from OntoDAG (`ontodag.sharing`, 0.28); the site keeps only its policies

## Where we stopped (2026-09-24)

- **Waiting on a decision:** how a store marks its principals — OntoDAG's
  `docs/plans/SHARING.md` Q1 (options, the collision example, leaning (b):
  declare them under a `principal` node, like dimensions). When decided:
  the site declares each address once when it first appears in a store,
  and OntoDAG can then report losses in `--dry-run` without being told
  whom to ask about.
- **Owed in OntoDAG's family:** an ontodag-fs release raising its ceiling
  above `ontodag<0.27` (its suite passes against 0.28).
- **Still in the site but generic:** the multi-store view (`views.py`,
  SHARING step 3, filtered overlays), the public-chain copy
  (`ontology.context`), pictures from a view (`picture.py`).

## Next

- [ ] Decide whether personas may shadow a public name (DESIGN §13)
- [ ] Suggest addresses already in your store while typing one (DESIGN §10)
- [ ] Editing the public store through `maintain-packs` (DESIGN §7); pack upgrades refreshing the public chains stores keep
- [ ] Account deletion (its address stays reserved)

## Walls and inboxes (design: DESIGN.md §14; canonical: OntoDAG docs/plans/WALLS_AND_INBOXES.md)

- [ ] `everyone` as a principal every reader holds, visitors included
- [ ] Posting: a post box with an audience picker (one person, a group, everyone), filed under `posted(now)`
- [ ] A wall page per account, and an inbox page per reader, newest first, with filters by author and category
- [ ] Waits on OntoDAG: `posted` declared where stores can adopt it, and `sharing.timeline`

## Later

- [ ] Write access for others: "share with edit", e.g. a department head managing Acme's `sales`
- [ ] Contributions: members filing their own items into a shared category
- [ ] Cross-store names: filing your note under a node shared with you, or hiding one of a sender's groups. Also the way to company packs: employees file under Acme's own categories instead of each keeping a copy
- [ ] Unlinkable pseudonyms: addresses that don't reveal the account behind them
- [ ] Other sites: addresses at other domains
- [ ] Messaging: threads, replies, notifications
