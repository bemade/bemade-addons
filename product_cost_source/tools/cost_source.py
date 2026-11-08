# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Value objects describing where a cost came from.

These are plain Python, not records. A cost source is a statement about a
moment in time -- "this vendor price, in force until then, covering this much
of the demand" -- and nothing about it wants to be stored.
"""

from dataclasses import dataclass, field

#: Confidence levels, worst first. A resolution is as weak as its weakest
#: source, so "worst" is ``min`` over this order.
CONFIDENCE_ORDER = ["unknown", "estimated", "indicative", "firm"]


@dataclass
class CostSource:
    """One contribution to a resolved cost.

    :param key: machine name of the source ('stock', 'vendor', ...). Never
        shown to a user; the evidence sentence is what a user reads.
    :param qty: how much of the demand this source covers.
    :param unit_price: price per unit, already in the requested currency.
    :param priced_on: the date this price was last *established*, or None when
        that cannot be determined. None is not a synonym for old -- it means
        unknown, and unknown is never treated as fresh.
    :param in_force_until: end of the agreement backing this price, when there
        is one. None means either no agreement or an open-ended one; see
        ``in_force``.
    :param in_force: whether an agreement covers the requested date. A price
        that is in force is firm regardless of its age.
    :param indicative: a price a vendor quoted but nobody confirmed (an open
        request for quotation, say). Better than a guess, worse than a
        promise: it never ranks above firm evidence.
    :param reference: a human reference for the evidence (an order number),
        used in the sentence describing it. Never a technical key.
    :param notes: other evidence worth mentioning beside this one, e.g. a
        newer quotation that did not win because a firm price exists.
    """

    key: str
    qty: float
    unit_price: float
    priced_on: object = None
    in_force_until: object = None
    in_force: bool = False
    indicative: bool = False
    reference: str = ""
    notes: list = field(default_factory=list)

    @property
    def subtotal(self):
        return self.unit_price * self.qty


@dataclass
class CostResolution:
    """A resolved cost together with the evidence for it."""

    unit_cost: float = 0.0
    confidence: str = "unknown"
    sources: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def is_firm(self):
        return self.confidence == "firm"
