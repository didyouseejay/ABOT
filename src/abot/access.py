"""Pedestrian access taxonomy from OSM tags (Milestone 04 methodology review; reporting only).

Four questions are kept apart:
  physical connectivity     whether mapped geometries share nodes (judged from topology, never here)
  mapped access status      what the `access` / `foot` tags (and `service=private`) say
  public pedestrian status  whether the general public may walk it, as far as the tags say
  authorized group          which users a restriction admits, as far as the tags name them

Tags are mapped claims, not site facts. The road class (`highway=*`) never changes the result: a
private `service` road is not thereby a residents' road, and a `tertiary` road tagged `access=private`
is private. Missing tags, or a missing gate, are not evidence of public access. Nothing here changes
routing: the active walk network still follows the osmnx filter (docs/METHODOLOGY.md §3.1).

Precedence (first match wins):
  1. `foot=*` decides for pedestrians. A public foot value (yes, designated, permissive, public,
     official) with a group restriction in `access` (private, residents, customers) is a conflict:
     `pedestrian_override`, flagged, never plain public. With any other `access` value (no, a vehicle
     category) the foot value is the standard pedestrian override and the result is `public`.
  2. Otherwise `access=*` decides.
  3. Otherwise `service=private` (a road-function subtag implying private use) gives `private`.
  4. Otherwise `untagged`: no restriction mapped, not verified.
"""

from __future__ import annotations

PUBLIC_VALUES = {"yes", "designated", "permissive", "public", "official"}
# General restrictions to a group of users: a public foot value next to one of these is a conflict.
GROUP_RESTRICTIONS = {"private", "residents", "customers"}
NAMED = {"no": "no", "private": "private", "residents": "residents", "customers": "customers",
         "destination": "destination"}  # fmt: skip

# Most restrictive first (RANK). A merged (simplified) edge takes the most restrictive status of its ways.
ACCESS_CLASSES = ["no", "private", "residents", "customers", "unknown", "destination", "pedestrian_override",
                  "untagged", "public"]  # fmt: skip
RANK = {c: i for i, c in enumerate(ACCESS_CLASSES)}
# Component rules (components.classify_component): restricted, and customers/unknown, by length share.
RESTRICTED = {"no", "private", "residents"}
CUSTOMERS_UNKNOWN = {"customers", "unknown"}

PUBLIC_PEDESTRIAN = {
    "no": "prohibited",
    "private": "not_public",
    "residents": "not_public",
    "customers": "customers_only",
    "unknown": "unknown",
    "destination": "destination_only_assumed",
    "pedestrian_override": "permitted_by_foot_tag_conflicting",
    "untagged": "not_restricted_by_tags_unverified",
    "public": "permitted_by_tag",
}
GROUP = {
    "no": "none_permitted",
    "private": "unspecified",  # access=private does not say who is authorised
    "residents": "residents_named_by_tag",
    "customers": "customers_named_by_tag",
    "unknown": "unknown",
    "destination": "destination_traffic",
    "untagged": "not_applicable",
    "public": "not_applicable",
}
VERIFY = {"private", "residents", "customers", "unknown", "pedestrian_override"}
# Approved for analysis and reporting only. Routing is NOT changed.
POLICY = {
    "public": "permitted by tag (yes/designated/permissive/public/official); permissive permission may be "
    "withdrawn; mapped permission is not verified real-world access",
    "untagged": "no access tag: OSM default for the highway class, not verified; not evidence of public access",
    "pedestrian_override": "conflicting tags: a group restriction in access with a public foot value; not "
    "treated as unrestricted public access; field verification required",
    "destination": "retained under the destination-access assumption (entering to reach a destination, not "
    "through-walking)",
    "unknown": "unknown restriction (permit, delivery, unknown, other values): flag for review",
    "customers": "customers only: retained only under a documented customer-access assumption; flagged",
    "residents": "restricted to residents, as named by the tag; not public",
    "private": "private: restricted to users the owner authorises; the tag names no group; not public",
    "no": "prohibited for pedestrians by tag (access=no without a pedestrian override, or foot=no)",
}


def access_assessment(tags: dict, gate: bool = False) -> dict:
    """Mapped access status of one way (or, with gate=True, one gate node) with its derived statuses
    and a traceable reason. Pure function of the tags."""
    foot, acc, hw = tags.get("foot"), tags.get("access"), tags.get("highway")
    notes = []
    if foot is not None:
        deciding = f"foot={foot}"
        if foot in PUBLIC_VALUES:
            cls = "pedestrian_override" if acc in GROUP_RESTRICTIONS else "public"
        else:
            cls = NAMED.get(foot, "unknown")
        if acc is not None:
            notes.append(f"the pedestrian tag foot={foot} takes precedence over access={acc}")
        if cls == "pedestrian_override":
            notes.append(f"conflict: access={acc} restricts general use while foot={foot} permits pedestrians; "
                         "not treated as unrestricted public access")  # fmt: skip
    elif acc is not None:
        deciding = f"access={acc}"
        cls = "public" if acc in PUBLIC_VALUES else NAMED.get(acc, "unknown")
    elif tags.get("service") == "private":
        deciding, cls = "service=private", "private"
        notes.append("service=private is a road-function subtag implying private use, not an access tag")
    else:
        deciding, cls = "none", "untagged"
        notes.append("no access or foot tag: not evidence of public access")
    if "permissive" in (foot, acc) and cls in ("public", "pedestrian_override"):
        notes.append("permissive: the owner permits passage, which may be withdrawn")
    if cls == "private":
        notes.append("the tag names no authorised group")
    if gate:
        notes.append("a mapped gate is an access-control point; its operating rules (hours, pedestrian passage) "
                     "are not mapped")  # fmt: skip
        if "locked" in tags:
            notes.append(f"locked={tags['locked']} (mapped)")
    if hw is not None:
        notes.append(f"highway={hw} recorded, not used")
    if cls == "pedestrian_override":
        group = GROUP[acc]  # pyright: ignore[reportArgumentType]  (acc is set: see the foot branch)
    else:
        group = GROUP[cls]
    return {
        "mapped_access_status": cls,
        "deciding_tag": deciding,
        "public_pedestrian_status": PUBLIC_PEDESTRIAN[cls],
        "authorized_group": group,
        "field_verification_required": cls in VERIFY or (gate and cls in ("untagged", "destination")),
        "classification_reason": "; ".join([f"{deciding} -> {cls}", *notes]),
    }


def access_class(tags: dict) -> str:
    """Mapped access status of one way or gate node (see access_assessment)."""
    return access_assessment(tags)["mapped_access_status"]


def most_restrictive(classes) -> str:
    return min(classes, key=RANK.__getitem__)


def way_tag_flags(tags: dict) -> set[str]:
    """Raw restriction tags of a way, for the removal scenarios (a foot tag overrides access)."""
    out = set()
    if "foot" not in tags:
        for v in ("no", "private", "destination", "customers"):
            if tags.get("access") == v:
                out.add(f"access={v}")
    if tags.get("foot") in ("no", "private"):
        out.add(f"foot={tags['foot']}")
    return out


def gate_tag_flags(tags: dict) -> set[str]:
    """Raw-tag removal-scenario flag of a gate node. Defined on tags, not on the status, so the
    scenario definitions in access_impact.csv do not move when the status labels change."""
    foot, acc = tags.get("foot"), tags.get("access")
    if foot is not None:
        return {"no": {"gate ineligible"}, "private": {"gate ineligible"}, "residents": {"gate private"}}.get(
            foot, set()
        )
    if acc is None:
        return {"gate private"} if tags.get("service") == "private" else {"gate untagged"}
    if acc in ("private", "residents"):
        return {"gate private"}
    return {"gate ineligible"} if acc == "no" else set()
