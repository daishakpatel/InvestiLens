"""Phrase patterns for the text-based red-flag rules (Phase 7e, FR-RF-003/004/005, ADR-0043).

Every pattern is a compiled regex with a comment and an example it matches. They are part of
`red_flag_taxonomy_v1`: changing one changes which flags fire, so it bumps `TAXONOMY_VERSION`.
Matching is per sentence, case-insensitive, on filing text that is untrusted data (never
instructions). No model judges anything here.
"""

from __future__ import annotations

import re

_I = re.IGNORECASE

# Sentence boundary: a full stop, question or exclamation mark followed by space and a capital.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"“])")

# --- Going concern (ASC 205-40 wording) -----------------------------------------------------
# The core: "substantial doubt … ability to continue as a going concern" in one sentence.
# e.g. "These conditions raise substantial doubt about the Company's ability to continue as a
# going concern."
GOING_CONCERN = re.compile(r"substantial\s+doubt\b.*\bgoing\s+concern", _I | re.S)

# Negation: the doubt is denied, or something already removed it.
# e.g. "There is no substantial doubt about our ability to continue as a going concern."
# e.g. "These events did not raise substantial doubt about our ability to continue as a going
# concern."  e.g. "The financing alleviated substantial doubt about …"
GC_NEGATION = re.compile(
    r"\b(?:no|not|never|without|neither)\b(?:\W+\w+){0,4}?\W+substantial\s+doubt"
    r"|\balleviated\s+(?:the\s+)?substantial\s+doubt"
    r"|substantial\s+doubt\b.{0,80}?\b(?:does|did|do)\s+not\s+exist",
    _I | re.S,
)

# Policy description: how the company evaluates going concern, not a conclusion.
# e.g. "Management evaluates whether there are conditions that raise substantial doubt about the
# Company's ability to continue as a going concern within one year."
GC_POLICY = re.compile(
    r"\b(?:evaluat\w*|assess\w*|consider\w*)\b.{0,60}?\bwhether\b.{0,80}?substantial\s+doubt",
    _I | re.S,
)

# Hypothetical / risk-factor language: a condition or modal before the doubt.
# e.g. "If we are unable to obtain financing, there could be substantial doubt about our ability
# to continue as a going concern."
GC_HYPOTHETICAL = re.compile(
    r"\b(?:if|unless|should|could|may|might|would)\b.{0,160}?substantial\s+doubt",
    _I | re.S,
)

# Alleviated by management's plans (ASC 205-40-50-12): the doubt existed, plans address it.
# e.g. "Substantial doubt about the Company's ability to continue as a going concern has been
# alleviated by management's plans."
GC_ALLEVIATED = re.compile(
    r"substantial\s+doubt\b.{0,160}?\b(?:alleviated|mitigated)\b.{0,60}?\bmanagement'?s?\s+plans?",
    _I | re.S,
)

# --- Material weakness (10-K Item 9A) -------------------------------------------------------
# A reported weakness: identified, existing, or controls concluded not effective.
# e.g. "Management identified a material weakness in our internal control over financial
# reporting related to revenue recognition."
MATERIAL_WEAKNESS = re.compile(
    r"\bmaterial\s+weakness(?:es)?\b.{0,160}?\b(?:identified|exist(?:s|ed)?|was|were|has\s+been|have\s+been)\b"
    r"|\b(?:identified|exist(?:s|ed)?)\b.{0,80}?\bmaterial\s+weakness(?:es)?\b"
    # e.g. "… concluded that our internal control … was not effective because of the material
    # weakness described below."
    r"|\bnot\s+effective\b.{0,160}?\bmaterial\s+weakness(?:es)?\b",
    _I | re.S,
)

# Not a reported weakness: the definition every 10-K quotes, a denial, or a hypothetical.
# e.g. "A material weakness is a deficiency, or a combination of deficiencies, …"
# e.g. "We did not identify any material weaknesses."  e.g. "… could result in a material weakness."
MW_NOT_REPORTED = re.compile(
    r"^\s*a\s+material\s+weakness\s+is\b"
    r"|\b(?:no|not|any|did\s+not\s+identify|not\s+aware\s+of)\b(?:\W+\w+){0,3}?\W+material\s+weakness"
    r"|\b(?:if|could|may|might|would)\b.{0,100}?material\s+weakness"
    r"|\bmaterial\s+weakness(?:es)?\b.{0,80}?\bremediated\b",
    _I | re.S,
)

# --- Executive departure (8-K Item 5.02) ----------------------------------------------------
# A departure verb. The item title ("Departure of Directors or Certain Officers; …") is removed
# before matching, so the heading alone never fires.
# e.g. "On March 2, 2026, Jane Doe notified the Company of her decision to resign as Chief
# Financial Officer."
DEPARTURE = re.compile(
    r"\b(?:resign(?:s|ed|ing|ation)?|retire(?:s|d|ment)?|retiring|terminat(?:ed|ion)|"
    r"step(?:s|ped|ping)?\s+down|depart(?:s|ed|ure)|separat(?:ed|ion)\s+from|"
    r"(?:will\s+)?not\s+(?:to\s+)?stand\s+for\s+re-?election)\b",
    _I,
)

# Not a departure: the terms of an award or agreement ("if she resigns for good reason", "vests
# upon retirement") or a biography ("previously served as … until his retirement", "has three
# decades of experience, most recently as CEO of …").
# e.g. "The award vests in full upon his retirement after the first anniversary of the grant."
DEPARTURE_NOT_EVENT = re.compile(
    r"\b(?:if|in\s+the\s+event|unless|would|eligible|vest(?:s|ed|ing)?|awards?|grant(?:s|ed)?|"
    r"severance|good\s+reason|without\s+cause|previously|formerly|served\s+as|has\s+served|"
    r"prior\s+to\s+joining|experience|most\s+recently)\b",
    _I,
)

# Item 5.02's own title, in case a filer's wording kept it from being stripped.
# e.g. "Departure of Directors or Principal Officers; Election of Directors"
ITEM_502_HEADING = re.compile(r"^\s*departure\s+of\s+directors\b", _I)

# Roles named in the same sentence as the departure (Form 8-K Item 5.02(b)). Names are never
# extracted. e.g. "… resign as Chief Financial Officer …" -> CFO.
ROLES: dict[str, re.Pattern[str]] = {
    "CEO": re.compile(
        r"\bchief\s+executive\s+officer\b|\bprincipal\s+executive\s+officer\b|\bCEO\b", _I
    ),
    "CFO": re.compile(
        r"\bchief\s+financial\s+officer\b|\bprincipal\s+financial\s+officer\b|\bCFO\b", _I
    ),
    "COO": re.compile(
        r"\bchief\s+operating\s+officer\b|\bprincipal\s+operating\s+officer\b|\bCOO\b", _I
    ),
    "CAO": re.compile(
        r"\bchief\s+accounting\s+officer\b|\bprincipal\s+accounting\s+officer\b|\bCAO\b", _I
    ),
    # The president, not a vice president. e.g. "President and Chief Operating Officer"
    "President": re.compile(r"(?<!vice )(?<!vice-)\bpresident\b", _I),
    "Director": re.compile(r"\bdirector\b|\bboard\s+of\s+directors\b|\bthe\s+board\b", _I),
}


# Words whose full stop does not end a sentence. e.g. "On May 1, 2026, Mr. Smith resigned."
ABBREVIATION = re.compile(
    r"(?:\b(?:Mr|Mrs|Ms|Dr|Jr|Sr|Inc|Corp|Co|Ltd|No|Nos|U\.S|e\.g|i\.e|vs|St)|\b[A-Z])\.$"
)


def sentences(text: str) -> list[str]:
    """Split text into sentences on punctuation followed by a capital, not after an
    abbreviation or an initial; blank lines split too."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        pending = ""
        for piece in SENTENCE_SPLIT.split(" ".join(block.split())):
            pending = f"{pending} {piece}".strip() if pending else piece.strip()
            if pending and not ABBREVIATION.search(pending):
                out.append(pending)
                pending = ""
        if pending:
            out.append(pending)
    return out
