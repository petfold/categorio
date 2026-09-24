# categor.io — design

Status: agreed 2026-09-24 and built in `categorio/`, except where a
section says otherwise. Decisions made while building are folded in: your
home is your address (§4), public names in your store (§3), sharing
accepts (§6), self-contained exports (§8).

## 1. The idea in one paragraph

Every account keeps one ordinary OntoDAG store. The public packs are one
more store, readable by everyone. Nothing else exists: no folders, no
permission table, no sharing records. **What is below you is what you
have.** To share something, you file it under the person you share it with.
A group is just a category you file under several people. A permission is a
category. What anyone can see follows from one rule, answered by OntoDAG
itself (`get`), over each store separately.

## 2. Stores

| Store | Written by | Read by |
|---|---|---|
| **public** — the packs (`core`, the domain packs, the dimension and unit packs) | the site's maintainers | everyone, including visitors who are not signed in |
| **one per account** — `ada@categor.io`'s store | that account only | its owner in full; others only what §4 allows |

Each store is a plain OntoDAG store — an `rs:` store, so each account has
its own history and undo — and exports as an ordinary `.od` file that the
`odag` command line reads. There is no merged "world" graph. It would be
wrong, not just slow: OntoDAG's subsumption is transitive, so in one merged
graph Bob's `rex ⊑ dog` would put `rex` below everyone who can see `dog`.
Keeping stores separate is what makes classification private.

**Memory.** The public vocabulary is held once per server process and
shared by every reader (about 17 MB for all packs). Nothing copies it:
pack pages read their top categories from the pack's entry list, and a
pack download is built when asked for. A user's store holds only what they
filed and the public chain above it, typically around 100 kB. The most
recently used stores stay in memory, within limits on their number and
total size, and the rest reload from disk when needed. So "not loading" a
pack has no meaning here, as it would on your own computer: its categories
are there either way, and the part of a pack that is really *yours*, the
names you used, is already all your store holds.

SQL holds only the login records: username and password hash; every
address ever registered, so none is reused; and what already sat below an
address in other stores when it was registered (§10). It also keeps an
index of which stores mention which address, so that finding your senders
doesn't mean opening every store. The index is derived from the stores and
can be rebuilt from them.

## 3. Names

Three kinds of name, told apart by spelling alone, with no new syntax:

| Spelling | What it is | Example |
|---|---|---|
| a bare name found in the public store | the shared vocabulary, one node for everyone, merged by name exactly as `odag pack core` merges locally | `dog`, `document`, `time(2026)` |
| any other bare name | your own category | `work`, `Japan trip`, `employee-information` |
| `name@categor.io`, `name+tag@categor.io` | an address: an account, or one of its categories | `ada@categor.io`, `ada+work@categor.io` |

Why addresses look like email:

- **They can't collide.** No vocabulary name contains `@`, but plain
  usernames would. Nine of 24 common ones tested (rose, grace, hope, mark,
  will, joy, olive, apple, mercury) are already categories in the packs,
  and suffixes fail too (`savings-account` is a category).
- **They can't be mistaken for terms.** `head(value)` means something
  computed in OntoDAG — `from(Paris)`, `to(London)`, `unit-family(BTC)` —
  so `account(ada)` would look like a term without being one.
- **They're familiar, and they leave room for other sites** (another domain).

To OntoDAG an address is an ordinary name. The interface shows it as `ada`,
or as `ada+work` for an address tied to a category.

**A public name in your store is the public category.** If you add
`work`, you get the vocabulary's `work` (an activity), not a new one. What
you file under it stays yours, as with any public category. On a category
of yours, the page lists your things first and folds the vocabulary's
subcategories behind a link, so a persona called `work` isn't buried under
406 public ones. Whether personas should be able to shadow a public name
is an open question (§13).

A handful of **setting names** are fixed by the site and used in your own
store: `hide-requests`, `show-requests`, `blocked`, and in the public store
`maintain-packs`. A test checks that no pack uses them.

## 4. Seeing: the rule

For another account O and you:

> You see node *x* of O's store if *x* is below one of your addresses **in
> O's store**, and O's address is filed in **your** store (not under
> `blocked`).

The first half is O sharing with you. The second half is you accepting O.
Each half is an ordinary edge in its owner's store, and each side controls
only its own half. Mechanically, what O shares with you is everything below
your addresses in O's store, the same cone `O.get([your address])` returns,
walked so as to skip what §10 excludes.

Everything else follows from the rule.

- **Parents stay closed.** Acme filing `employee-information` under its
  private `merger-plans` exposes nothing: a parent is not below you. A
  shared node shows only those parents you could see anyway (the public
  `document`, or another node shared with you).
- **Members don't see each other.** Members sit *above* a group, you see
  only what is *below* you. Ada sees `employees` and what is filed under
  it, never Bob. Only the owner sees who is in a group.
- **Your filings are yours.** `rex ⊑ dog` in your store shows `rex` to no
  one, because nobody else reads your store except through the rule.
- **No pushing into others' groups.** Eve's edges live in Eve's store, so
  she can't put anything into Acme's `employees`.
- **Your own view** is your whole store, the public store, and everything
  shared with you and accepted.
- **Your home is your own address.** A category you add at the top is
  filed under `ada@categor.io` in your own store. That shares it with no
  one, because only edges in *other* stores count towards what you see.

## 5. Sharing, groups, departments

Sharing means filing under an address. Checked in OntoDAG:

```
# acme@categor.io's store
employees ada@categor.io bob@categor.io harry@categor.io   # a group: filed under its members
sales harry@categor.io                                     # a department
employees sales                                            # sales sees all that employees see
employee-information employees                             # shared with the group
handbook employee-information document                     # part of it, and a document
sales-leads sales
employee-information merger-plans                          # a private parent: stays hidden
```

Ada sees `employees`, `employee-information`, `handbook`. Harry also sees
`sales`, `sales-leads`. Nobody sees `merger-plans` or the other members.

- **Groups nest the opposite way to Linux.** More access means more below
  you, so `employees ⊑ sales` reads "sales has everything employees have".
  Everyone in sales then sees the employee material, and nobody outside
  sales sees the sales material.
- **A group is just a category.** Whatever you file under a group, its
  members see. Anything can be a group; its name is visible to its members,
  so name it accordingly.
- **Share with one person** by filing an item directly under their address.

## 6. Receiving: acceptance, requests, blocking

Every share is a push: filing under someone puts it in their home, and so
does adding them to a group. Consent is the second half of the rule in §4.

- **Accepting O** means filing `O's address` in your store. Where you file
  it is where O's shares appear: `acme@categor.io ⊑ work` puts everything
  Acme shares with you into `work`, and nothing of Acme's into `hobby`.
  You can file O under a category of contacts (`colleagues ⊑ work`); only
  your own store sees that.
- **Requests.** When O shares with you and you haven't filed O anywhere,
  you see a request showing O's name and how many items, but no content.
  You can accept it (choosing where to file O), block it, or leave it
  pending.
- **Blocking** is `O's address ⊑ blocked`: no requests, nothing shown.
  Unblocking is unfiling it.
- **The sender learns nothing.** O can't read your store, so it never
  learns whether you accepted.
- **Sharing with someone accepts them.** Filing something under Bob's
  address puts that address in your store, and that is what accepting
  means. You started the exchange, so his shares appear without a request.
  Blocking still works: `bob@categor.io ⊑ blocked` hides his shares, and
  what you share with him is unchanged.

### Addresses tied to categories

Besides your account address, you can create addresses tied to a category,
`ada+work@categor.io`, by filing the address under that category:

```
# ada@categor.io's store
ada+work@categor.io work            # what arrives here appears in work
hide-requests ada+work@categor.io   # this address: accepted senders only
acme@categor.io work                # acme accepted, its shares land in work
```

- **Things arrive where they were addressed.** Anything shared with
  `ada+work` appears under `work`, before you even file its sender.
- **Request settings are per address.** Under an address,
  `hide-requests` or `show-requests` sets whether unknown senders produce
  requests there. The nearest setting wins: the address's own, then your
  account's (filed under `ada@categor.io`), then the default, which is
  **show**.
- **So the category is what you give out.** A public address for strangers
  can show requests, while one you give only to colleagues hides them.

An address like `ada+work` is visibly linked to `ada`. Unlinkable
pseudonyms are on the roadmap.

## 7. Writing

- **You write only your own store.** Any edge, any name.
- **Your store can refer to** your own categories, the vocabulary, and
  addresses. It can't refer to another account's categories. That would
  need cross-store names, which are on the roadmap. You also never see a
  category that isn't shared with you (§4).
- **The public store** is written by accounts that have `maintain-packs`
  below them there. Capabilities work the same way everywhere: what is
  below you is what you have. Pack updates from OntoDAG are merged in.
  *Not built yet:* the public store is built from the released packs at
  startup, and nobody edits it through the site.

## 8. Files

- **Export** can also include whole packs. The file then carries each chosen
  pack complete, merged in as `odag pack NAME` would, for use with `odag`
  elsewhere. It's built when you download it; nothing is added to your store.
- **Export** writes your store as `.od`, and the file is self-contained.
  Your store keeps the public ancestors of every public category you use,
  as `odag excerpt --context` does (`rex ⊑ dog` brings `dog`'s chain up to
  `organism`). So `odag -f ada.od get animal` finds `rex` with no pack
  installed. Addresses appear as themselves.
- **Import** merges an `.od` file into your store, with a preview of what
  would arrive (`merge --diff`). Nothing in a file you import can grant
  you anything: the only edges that grant sight live in the sharer's store.
- **Public packs** download as `.od` files, as they do now.

## 9. Known behaviours

- **Redundant shares vanish when a group changes.** OntoDAG keeps only the
  transitive reduction. If Acme shares a node with Ada directly and also
  through `employees`, the direct edge is redundant and dropped, so later
  removing Ada from `employees` removes both. Every unfiling in OntoDAG
  behaves this way. Mitigation: before an unfile, move or remove, the site
  lists who would stop seeing what, by comparing the §4 queries before and
  after on a copy.
- **Accepting is per sender, or per address.** You can't hide one of Acme's
  groups while keeping the rest; that needs cross-store names (roadmap).
- **The sender sees whom it shared with.** Those are its own edges; it never
  sees whether you accepted.
- **Addresses are never listed.** To share with someone you must know
  their address, and nothing on the site lists accounts.
- **Shares through groups have no edge of their own.** For the same
  reduction reason, `employees ⊑ harry` disappears once `employees ⊑ sales
  ⊑ harry` implies it. The owner's page therefore lists everyone a
  category reaches, marking those who get it "through a group".

## 10. Sharing with an address that doesn't exist

**Refused silently.** The share simply doesn't happen, now or ever, and
the sender isn't told.

- **The filing stays in the sender's store.** Removing it would tell the
  sender the address doesn't exist.
- **It never grants anything,** not even to someone who registers that
  name later. A permission can't wait for its holder to appear: that
  would make unregistered names a hunting ground, with whoever claims a
  name first receiving what was filed under it.

Refusing openly was rejected because it lets anyone test which addresses
exist. Keeping such shares silently was rejected because a later
registrant of the name would receive them.

What this takes:

- **Nothing can differ.** Existing and unknown addresses must behave the
  same in every response, status and timing. There is no "delivered" state
  anywhere; the interface says "shared with", never "delivered".
- **Typos stay invisible, as non-acceptance already is.** A sender can't
  tell a typo from a recipient who hasn't accepted or has blocked them.
  So the site flags an address that's new to the sender's store:
  "bob@categor.io is new in your store — check the spelling". (Suggesting
  addresses already in the store as you type is not built yet.)
- **Shares made before registration never count.** A share is an edge in
  the sender's store, and §4 is evaluated each time someone reads. So at
  registration the site records, for every store that mentions the new
  address, what was below it at that moment. That never counts, and the
  §4 walk doesn't pass through it. (This records the state itself rather
  than a store version, so no history lookup is needed.) One case falls
  out: re-sharing a node that was already filed under the address before
  it existed won't deliver it.
- **Addresses are never reused.** Once registered, an address can't be taken
  again after the account is deleted, or a new owner would inherit the old
  one's shares.

## 11. What this replaces in the prototype

- **Private ontologies** stored as SQL rows become one store per account.
- **"Merge a pack"** disappears: the vocabulary is always there, you just
  file under it.
- **The ontology list** becomes your categories: `work`, `hobby` and so on
  are your personas.
- **SQL** shrinks to logins.

## 12. Pictures and the console

**Pictures show what the page shows.** A picture draws one category with
its parents and children, in the style of OntoDAG's visualiser (Graphviz
`dot`). It is drawn from the viewer's view, never from a store, because a
store's picture would show edges the viewer may not see: a shared
category's private parents, or the other members of a group. Names are
never markup. Graphviz escapes them in its SVG, and they are passed as
plain text rather than Graphviz HTML labels.

**The console runs a safe subset of the `odag` command language.**
OntoDAG's own web app runs a subset over an in-memory sandbox; here the
stores are real, so the rules are stricter:

| Commands | Where they run | Why |
|---|---|---|
| `get` `count` `list` `show` `below` `?` `overlapping` `overlaps` `meet` `canon` `help` | your store, or the public vocabulary; visitors get the vocabulary only | questions: they change nothing (checked afterwards: if the node count changed, the store is reloaded and the vocabulary rebuilt) |
| `put` `move` `remove` | your store only | tried on a copy first; an address of another site is refused; a change that stops someone seeing something waits for "Run anyway" (§9) |
| `history` `status` `undo` `redo` | your store only | the same history as the Store page |
| `import` `merge` `ingest` `export` `excerpt` `diff` `visualize` `-o FILE` | nowhere | they read or write files on the server; the site has upload, download and pictures instead |
| `set` `swarm` `index` | nowhere | they change the server's settings, or reach out from it |
| `pack` (list), `pack NAME --show`, `--diff`, `prelude --show` | anyone; `--diff` on the chosen store | looking only |
| `pack NAME`, `prelude` | nowhere | adopting would copy the whole pack into your store, a second copy per user of what every store already shares (§2, memory). You use a pack by filing under its names; to take one away whole, **Store → Export** can include it in the file, merged on the way out |
| `web` | nowhere | it's what you're looking at |

The rule comes from OntoDAG, not from a list kept here: every OntoDAG
command declares what it touches (`reads`, `writes`, `versions`, `files`,
`network`, `settings`), and `effects(argv)` sharpens that for a whole line
(`-o FILE` adds `files`). A line runs here only if it touches nothing but a
store, so a command added to OntoDAG later is allowed or refused by its own
declaration. Each command runs against one DAG
through a session that never composes the server's `overlays`, so an
answer can't include another store. Writes also bring in what the buttons
would: the public ancestors of the names used, and this site's addresses
(as the Share button adds them). Every page has an **As a command** link
showing its question in this language.

## 13. Open question

**Should a persona be able to shadow a public name?** Today `work` in your
store *is* the vocabulary's `work`, merged by name as everywhere in
OntoDAG. That's consistent, and your things under it stay private. But it
says your payslips are a kind of the activity "work", and the page has to
fold 406 public subcategories out of the way. The alternative is to let a
category of yours shadow the public name in your store. But then two
different `work`s meet in every export and every query, which is exactly
the collision addresses were designed to avoid (§3).
