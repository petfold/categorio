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

## Next

- [ ] Decide whether personas may shadow a public name (DESIGN §12)
- [ ] Suggest addresses already in your store while typing one (DESIGN §10)
- [ ] Editing the public store through `maintain-packs` (DESIGN §7); pack upgrades refreshing the public chains stores keep
- [ ] Account deletion (its address stays reserved)

## Later

- [ ] Write access for others: "share with edit", e.g. a department head managing Acme's `sales`
- [ ] Contributions: members filing their own items into a shared category
- [ ] Cross-store names: filing your note under a node shared with you, or hiding one of a sender's groups
- [ ] Unlinkable pseudonyms: addresses that don't reveal the account behind them
- [ ] Other sites: addresses at other domains
- [ ] Messaging: threads, replies, notifications
