"""The three kinds of name (DESIGN §3), told apart by spelling alone.

- a bare name in the public store: the shared vocabulary;
- any other bare name: a category of the store it is in;
- `user@DOMAIN` or `user+tag@DOMAIN`: an address.

Plus the handful of setting names the site gives a meaning to.
"""

import re

DOMAIN = "categor.io"

USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_ADDRESS = re.compile(r"^([a-z0-9][a-z0-9._-]{2,31})(?:\+([a-z0-9][a-z0-9._-]{0,31}))?@"
                      + re.escape(DOMAIN) + r"$")

HIDE_REQUESTS = "hide-requests"
SHOW_REQUESTS = "show-requests"
BLOCKED = "blocked"
MAINTAIN_PACKS = "maintain-packs"
SETTINGS = frozenset({HIDE_REQUESTS, SHOW_REQUESTS, BLOCKED, MAINTAIN_PACKS})

ROOT = "*"


def address(user, tag=None):
    return f"{user}+{tag}@{DOMAIN}" if tag else f"{user}@{DOMAIN}"


def parse_address(name):
    """`(user, tag)` for an address of this site, else None."""
    m = _ADDRESS.match(name)
    return (m.group(1), m.group(2)) if m else None


def is_address(name):
    return "@" in name


def owner_of(name):
    """The username an address belongs to, or None."""
    parsed = parse_address(name)
    return parsed[0] if parsed else None


def short(name):
    """How an address is shown: `ada`, `ada+work`."""
    return name[:-len("@" + DOMAIN)] if name.endswith("@" + DOMAIN) else name


def check_category(name):
    """A name a user may give a category of their own. Raises ValueError."""
    if not name or name != name.strip():
        raise ValueError("a category needs a name without leading or trailing spaces")
    if len(name) > 200:
        raise ValueError("names are at most 200 characters")
    if name == ROOT or any(c in name for c in ",\n\r\t"):
        raise ValueError(f"{name!r} cannot be used as a category name")
    if "@" in name:
        raise ValueError(f"{name!r} looks like an address — names with @ are addresses only")
    if name in SETTINGS:
        raise ValueError(f"{name!r} is a setting name; use the settings instead")
    return name


def check_address(name):
    """A well-formed address of this site. Raises ValueError.

    Says nothing about whether the address is registered (DESIGN §10)."""
    name = name.strip().lower()
    if "@" not in name:
        name = f"{name}@{DOMAIN}"
    if parse_address(name) is None:
        raise ValueError(f"{name!r} is not a {DOMAIN} address")
    return name
