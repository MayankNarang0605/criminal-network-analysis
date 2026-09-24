"""
Indian penal-law knowledge base.

Maps IPC / BNS-2023 / special-act sections to crime domain, gravity and
women-safety relevance. Gravity drives offence-severity risk scoring; the
women-safety flags drive the Women Safety Division module, which is the
specific department that owns this problem statement.
"""
from __future__ import annotations

# gravity: 1 (petty) .. 10 (gravest). bailable/cognizable omitted for brevity.
SECTIONS: dict[str, dict] = {
    # --- Offences against the human body ---
    "302": {"desc": "Murder", "domain": "Violent Crime", "gravity": 10, "bns": "103"},
    "304": {"desc": "Culpable homicide not amounting to murder", "domain": "Violent Crime", "gravity": 8, "bns": "105"},
    "307": {"desc": "Attempt to murder", "domain": "Violent Crime", "gravity": 9, "bns": "109"},
    "323": {"desc": "Voluntarily causing hurt", "domain": "Violent Crime", "gravity": 3, "bns": "115"},
    "324": {"desc": "Hurt by dangerous weapon", "domain": "Violent Crime", "gravity": 5, "bns": "118"},
    "326A": {"desc": "Acid attack", "domain": "Crime Against Women", "gravity": 9, "bns": "124", "women_safety": True},
    "34": {"desc": "Acts done by several persons in furtherance of common intention", "domain": "Conspiracy", "gravity": 4, "bns": "3(5)"},

    # --- Crimes against women (Women Safety Division focus) ---
    "354": {"desc": "Assault on woman with intent to outrage modesty", "domain": "Crime Against Women", "gravity": 6, "bns": "74", "women_safety": True},
    "354A": {"desc": "Sexual harassment", "domain": "Crime Against Women", "gravity": 6, "bns": "75", "women_safety": True},
    "354B": {"desc": "Assault with intent to disrobe a woman", "domain": "Crime Against Women", "gravity": 7, "bns": "76", "women_safety": True},
    "354C": {"desc": "Voyeurism", "domain": "Crime Against Women", "gravity": 6, "bns": "77", "women_safety": True},
    "354D": {"desc": "Stalking", "domain": "Crime Against Women", "gravity": 6, "bns": "78", "women_safety": True},
    "375": {"desc": "Rape (definition)", "domain": "Crime Against Women", "gravity": 10, "bns": "63", "women_safety": True},
    "376": {"desc": "Punishment for rape", "domain": "Crime Against Women", "gravity": 10, "bns": "64", "women_safety": True},
    "376D": {"desc": "Gang rape", "domain": "Crime Against Women", "gravity": 10, "bns": "70", "women_safety": True},
    "498A": {"desc": "Cruelty by husband or relatives", "domain": "Crime Against Women", "gravity": 6, "bns": "85", "women_safety": True},
    "304B": {"desc": "Dowry death", "domain": "Crime Against Women", "gravity": 9, "bns": "80", "women_safety": True},
    "509": {"desc": "Word or gesture insulting modesty of a woman", "domain": "Crime Against Women", "gravity": 4, "bns": "79", "women_safety": True},

    # --- Trafficking and kidnapping ---
    "363": {"desc": "Kidnapping", "domain": "Human Trafficking", "gravity": 7, "bns": "137", "women_safety": True},
    "366": {"desc": "Kidnapping/abducting woman to compel marriage", "domain": "Human Trafficking", "gravity": 8, "bns": "87", "women_safety": True},
    "366A": {"desc": "Procuration of minor girl", "domain": "Human Trafficking", "gravity": 9, "bns": "96", "women_safety": True},
    "366B": {"desc": "Importation of girl from foreign country", "domain": "Human Trafficking", "gravity": 9, "bns": "141", "women_safety": True},
    "370": {"desc": "Trafficking of persons", "domain": "Human Trafficking", "gravity": 9, "bns": "143", "women_safety": True},
    "370A": {"desc": "Exploitation of a trafficked person", "domain": "Human Trafficking", "gravity": 9, "bns": "144", "women_safety": True},
    "372": {"desc": "Selling minor for prostitution", "domain": "Human Trafficking", "gravity": 10, "bns": "98", "women_safety": True},
    "373": {"desc": "Buying minor for prostitution", "domain": "Human Trafficking", "gravity": 10, "bns": "99", "women_safety": True},

    # --- Property and economic offences ---
    "379": {"desc": "Theft", "domain": "Property Crime", "gravity": 4, "bns": "303"},
    "380": {"desc": "Theft in dwelling house", "domain": "Property Crime", "gravity": 5, "bns": "305"},
    "384": {"desc": "Extortion", "domain": "Organised Crime", "gravity": 7, "bns": "308"},
    "386": {"desc": "Extortion by putting in fear of death", "domain": "Organised Crime", "gravity": 8, "bns": "308(3)"},
    "392": {"desc": "Robbery", "domain": "Property Crime", "gravity": 7, "bns": "309"},
    "395": {"desc": "Dacoity", "domain": "Organised Crime", "gravity": 9, "bns": "310"},
    "406": {"desc": "Criminal breach of trust", "domain": "Economic Offence", "gravity": 5, "bns": "316"},
    "409": {"desc": "Criminal breach of trust by public servant/banker", "domain": "Economic Offence", "gravity": 7, "bns": "316(5)"},
    "411": {"desc": "Dishonestly receiving stolen property", "domain": "Property Crime", "gravity": 4, "bns": "317"},
    "413": {"desc": "Habitually dealing in stolen property", "domain": "Organised Crime", "gravity": 7, "bns": "317(5)"},
    "420": {"desc": "Cheating and dishonestly inducing delivery of property", "domain": "Economic Offence", "gravity": 6, "bns": "318"},
    "467": {"desc": "Forgery of valuable security", "domain": "Economic Offence", "gravity": 8, "bns": "337"},
    "468": {"desc": "Forgery for purpose of cheating", "domain": "Economic Offence", "gravity": 6, "bns": "336(3)"},
    "471": {"desc": "Using forged document as genuine", "domain": "Economic Offence", "gravity": 6, "bns": "340"},

    # --- Conspiracy / obstruction ---
    "120B": {"desc": "Criminal conspiracy", "domain": "Organised Crime", "gravity": 7, "bns": "61(2)"},
    "201": {"desc": "Causing disappearance of evidence", "domain": "Obstruction", "gravity": 5, "bns": "238"},
    "212": {"desc": "Harbouring an offender", "domain": "Obstruction", "gravity": 5, "bns": "249"},
    "506": {"desc": "Criminal intimidation", "domain": "Violent Crime", "gravity": 5, "bns": "351(2)"},

    # --- IT Act ---
    "66C": {"desc": "Identity theft (IT Act)", "domain": "Cyber Crime", "gravity": 6, "act": "IT Act 2000"},
    "66D": {"desc": "Cheating by personation using computer (IT Act)", "domain": "Cyber Crime", "gravity": 6, "act": "IT Act 2000"},
    "66E": {"desc": "Violation of privacy (IT Act)", "domain": "Cyber Crime", "gravity": 6, "act": "IT Act 2000", "women_safety": True},
    "67": {"desc": "Publishing obscene material (IT Act)", "domain": "Cyber Crime", "gravity": 6, "act": "IT Act 2000", "women_safety": True},
    "67A": {"desc": "Publishing sexually explicit material (IT Act)", "domain": "Cyber Crime", "gravity": 7, "act": "IT Act 2000", "women_safety": True},

    # --- NDPS Act ---
    "21": {"desc": "Contravention re manufactured drugs (NDPS)", "domain": "Narcotics", "gravity": 8, "act": "NDPS Act 1985"},
    "22": {"desc": "Contravention re psychotropic substances (NDPS)", "domain": "Narcotics", "gravity": 8, "act": "NDPS Act 1985"},
    "25": {"desc": "Possession of prohibited arms (Arms Act)", "domain": "Arms Trafficking", "gravity": 7, "act": "Arms Act 1959"},
    "27": {"desc": "Using arms in contravention (Arms Act)", "domain": "Arms Trafficking", "gravity": 7, "act": "Arms Act 1959"},
    "29": {"desc": "Abetment and criminal conspiracy (NDPS)", "domain": "Narcotics", "gravity": 8, "act": "NDPS Act 1985"},

    # --- POCSO ---
    "POCSO-4": {"desc": "Penetrative sexual assault on child (POCSO)", "domain": "Crime Against Children", "gravity": 10, "act": "POCSO 2012", "women_safety": True},
    "POCSO-6": {"desc": "Aggravated penetrative sexual assault (POCSO)", "domain": "Crime Against Children", "gravity": 10, "act": "POCSO 2012", "women_safety": True},

    # --- PMLA ---
    "PMLA-3": {"desc": "Offence of money laundering (PMLA)", "domain": "Economic Offence", "gravity": 8, "act": "PMLA 2002"},
}


def lookup(section: str) -> dict:
    key = str(section).strip().upper().replace(" ", "")
    return SECTIONS.get(key, {
        "desc": f"Section {section}",
        "domain": "Unclassified",
        "gravity": 4,
    })


def gravity_of(sections: list[str]) -> int:
    """Highest gravity across the charged sections."""
    if not sections:
        return 0
    return max(lookup(s).get("gravity", 4) for s in sections)


def domains_of(sections: list[str]) -> list[str]:
    seen: list[str] = []
    for s in sections:
        d = lookup(s).get("domain", "Unclassified")
        if d not in seen:
            seen.append(d)
    return seen


def is_women_safety(sections: list[str]) -> bool:
    return any(lookup(s).get("women_safety") for s in sections)


def describe(sections: list[str]) -> list[dict]:
    out = []
    for s in sections:
        info = lookup(s)
        out.append({
            "section": s,
            "description": info.get("desc"),
            "domain": info.get("domain"),
            "gravity": info.get("gravity"),
            "bns_equivalent": info.get("bns"),
            "act": info.get("act", "Indian Penal Code 1860"),
            "women_safety": bool(info.get("women_safety")),
        })
    return out
