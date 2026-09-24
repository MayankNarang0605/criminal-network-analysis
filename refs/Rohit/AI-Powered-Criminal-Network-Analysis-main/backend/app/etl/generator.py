"""
Synthetic corpus generator with planted ground truth.

Why this exists: the ten sample FIRs are too small to demonstrate that the
analytics actually work. More importantly, on real data nobody knows the right
answer, so "our system found the kingpin" is an unfalsifiable claim.

This generator builds criminal networks with a *known* hierarchy — kingpin,
lieutenants, operatives, couriers, mules — and then emits only the observable
artefacts an investigator would actually receive (FIR narratives, CDRs, bank
transactions). The true roles are written to `ground_truth` and never exposed to
the analytics pipeline.

That gives a real evaluation: run the kingpin detector on the observable data and
measure whether it recovers the planted hierarchy. See app/analytics/evaluate.py.

Realism constraints modelled deliberately:
  * Kingpins are *not* the highest-degree nodes. They talk only to lieutenants.
  * Couriers and mules have high call/transaction volume — the naive decoy.
  * Communication is compartmentalised: operatives in different cells never talk.
  * Money flows down the hierarchy in fan-out; proceeds flow up via layering.
  * FIR text names lower-tier actors far more often than leadership, because
    that is who gets caught.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

FIRST_NAMES_M = [
    "Vikram", "Ramesh", "Sunil", "Deepak", "Mohan", "Farhan", "Sanjay", "Pappu",
    "Rajasekar", "Kannan", "Tapan", "Bittu", "Shankar", "Salim", "Akash", "Rohit",
    "Dinesh", "Jignesh", "Rajendra", "Imran", "Arun", "Suresh", "Manoj", "Ajay",
    "Vijay", "Anil", "Prakash", "Naveen", "Kiran", "Girish", "Harish", "Mukesh",
    "Nitin", "Pankaj", "Rakesh", "Sachin", "Tarun", "Umesh", "Yogesh", "Bhavesh",
    "Chetan", "Devendra", "Gaurav", "Hemant", "Jatin", "Kapil", "Lalit", "Nikhil",
]
FIRST_NAMES_F = [
    "Priya", "Sunita", "Rekha", "Lakshmi", "Neha", "Kavita", "Anita", "Meena",
    "Pooja", "Sarita", "Usha", "Vandana", "Shalini", "Deepa", "Geeta", "Jyoti",
]
SURNAMES = [
    "Desai", "Nair", "Gupta", "Yadav", "Thakur", "Kumar", "Sheikh", "Mishra",
    "Singh", "Mondal", "Roy", "Das", "Khan", "Verma", "Joshi", "Patel", "Bhatt",
    "Prajapati", "Reddy", "Qureshi", "Gowda", "Sharma", "Patil", "Deshmukh",
    "Chauhan", "Rathore", "Saxena", "Agarwal", "Jain", "Malhotra", "Kapoor",
    "Banerjee", "Chatterjee", "Ghosh", "Iyer", "Menon", "Pillai", "Shetty",
]
ALIASES = [
    "Vicky", "Ramu", "DK", "MK", "Pappu", "Raja", "Tapan Da", "Danny", "Anna",
    "Bhai", "Chotu", "Guru", "Kaka", "Lala", "Munna", "Nana", "Seth", "Ustad",
]

CITIES = [
    ("Mumbai", "Maharashtra", "MH", 19.0760, 72.8777,
     ["Bandra West", "Andheri East", "Dadar", "Kurla", "Malad", "Borivali"]),
    ("Delhi", "Delhi", "DL", 28.6139, 77.2090,
     ["Saket", "Mehrauli", "Vasant Kunj", "Karol Bagh", "Rohini", "Dwarka"]),
    ("Bengaluru", "Karnataka", "KA", 12.9716, 77.5946,
     ["Whitefield", "Electronic City", "Koramangala", "Jayanagar", "Hebbal"]),
    ("Lucknow", "Uttar Pradesh", "UP", 26.8467, 80.9462,
     ["Aminabad", "Hazratganj", "Charbagh", "Gomti Nagar", "Alambagh"]),
    ("Chennai", "Tamil Nadu", "TN", 13.0827, 80.2707,
     ["T. Nagar", "Anna Nagar", "Adyar", "Velachery", "Guindy"]),
    ("Kolkata", "West Bengal", "WB", 22.5726, 88.3639,
     ["Park Street", "Howrah", "Salt Lake", "Dum Dum", "Behala"]),
    ("Jaipur", "Rajasthan", "RJ", 26.9124, 75.7873,
     ["MI Road", "Malviya Nagar", "Vaishali Nagar", "Jhotwara"]),
    ("Pune", "Maharashtra", "MH", 18.5204, 73.8567,
     ["Koregaon Park", "Hinjewadi", "Kothrud", "Hadapsar"]),
    ("Ahmedabad", "Gujarat", "GJ", 23.0225, 72.5714,
     ["Satellite", "SG Highway", "Maninagar", "Naranpura"]),
    ("Hyderabad", "Telangana", "TS", 17.3850, 78.4867,
     ["Jubilee Hills", "Banjara Hills", "Kukatpally", "Secunderabad"]),
]

BANKS = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "BOI", "UBI", "Canara", "Yes Bank"]

# Each network archetype: crime domain, IPC sections, size profile, narrative verbs.
ARCHETYPES = [
    {
        "domain": "Human Trafficking",
        "sections": ["370", "370A", "366", "363", "120B"],
        "cells": 3, "operatives_per_cell": (2, 4),
        "women_safety": True,
        "verbs": {"kingpin": "coordinates the interstate network from",
                  "lieutenant": "recruits victims from rural areas in",
                  "operative": "confines and guards victims at",
                  "courier": "transports victims between",
                  "mule": "receives and forwards proceeds through"},
    },
    {
        "domain": "Narcotics",
        "sections": ["21", "22", "29", "120B"],
        "cells": 3, "operatives_per_cell": (2, 4),
        "verbs": {"kingpin": "directs procurement and distribution from",
                  "lieutenant": "manages consignment logistics in",
                  "operative": "handles street-level distribution in",
                  "courier": "carries consignments between",
                  "mule": "launders sale proceeds via"},
    },
    {
        "domain": "Economic Offence",
        "sections": ["420", "467", "468", "471", "120B", "PMLA-3"],
        "cells": 2, "operatives_per_cell": (3, 5),
        "verbs": {"kingpin": "controls the shell company structure from",
                  "lieutenant": "onboards investors and manages agents in",
                  "operative": "prepares forged documentation at",
                  "courier": "collects cash deposits across",
                  "mule": "holds beneficiary accounts at"},
    },
    {
        "domain": "Cyber Crime",
        "sections": ["66C", "66D", "420", "120B"],
        "cells": 2, "operatives_per_cell": (2, 4),
        "verbs": {"kingpin": "operates the fraud infrastructure from",
                  "lieutenant": "supervises the calling floor in",
                  "operative": "conducts vishing calls from",
                  "courier": "withdraws funds from ATMs across",
                  "mule": "provides mule accounts at"},
    },
    {
        "domain": "Organised Crime",
        "sections": ["384", "386", "506", "120B", "25"],
        "cells": 3, "operatives_per_cell": (2, 3),
        "verbs": {"kingpin": "heads the syndicate operating out of",
                  "lieutenant": "collects protection money in",
                  "operative": "delivers threats to businesses in",
                  "courier": "moves cash collections through",
                  "mule": "parks extortion proceeds in"},
    },
    {
        "domain": "Crime Against Women",
        "sections": ["354D", "354A", "509", "66E", "506"],
        "cells": 2, "operatives_per_cell": (2, 3),
        "women_safety": True,
        "verbs": {"kingpin": "organises the harassment campaign from",
                  "lieutenant": "identifies and profiles targets in",
                  "operative": "carries out stalking and intimidation in",
                  "courier": "delivers threatening material in",
                  "mule": "funds the operation through"},
    },
]


@dataclass
class Actor:
    actor_id: str
    name: str
    alias: str | None
    role: str            # kingpin | lieutenant | operative | courier | mule | peripheral
    network: str
    cell: int
    age: int
    gender: str
    city: str
    state: str
    phone: str
    account: str | None = None
    bank: str | None = None
    vehicle: str | None = None
    contacts: set[str] = field(default_factory=set)   # actor_ids
    reports_to: str | None = None


@dataclass
class Corpus:
    firs: list[dict] = field(default_factory=list)
    cdr: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)
    ground_truth: list[dict] = field(default_factory=list)
    actors: list[Actor] = field(default_factory=list)

    def summary(self) -> dict:
        roles: dict[str, int] = {}
        for gt in self.ground_truth:
            roles[gt["true_role"]] = roles.get(gt["true_role"], 0) + 1
        return {
            "firs": len(self.firs),
            "cdr_records": len(self.cdr),
            "transactions": len(self.transactions),
            "actors": len(self.actors),
            "networks": len({a.network for a in self.actors}),
            "role_distribution": roles,
        }


class CorpusGenerator:
    def __init__(self, seed: int = 20260828) -> None:
        self.rng = random.Random(seed)
        self._used_phones: set[str] = set()
        self._used_accounts: set[str] = set()
        self._used_names: set[str] = set()
        self._counter = 0

    # ------------------------------------------------------------------
    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:05d}"

    def _phone(self) -> str:
        while True:
            number = f"{self.rng.choice('6789')}{self.rng.randint(10**8, 10**9 - 1)}"
            if number not in self._used_phones:
                self._used_phones.add(number)
                return number

    def _account(self) -> str:
        while True:
            acct = str(self.rng.randint(10**10, 10**11 - 1))
            if acct not in self._used_accounts:
                self._used_accounts.add(acct)
                return acct

    def _name(self, gender: str) -> str:
        pool = FIRST_NAMES_F if gender == "Female" else FIRST_NAMES_M
        for _ in range(200):
            name = f"{self.rng.choice(pool)} {self.rng.choice(SURNAMES)}"
            if name not in self._used_names:
                self._used_names.add(name)
                return name
        return f"{self.rng.choice(pool)} {self.rng.choice(SURNAMES)} {self.rng.randint(1, 99)}"

    def _plate(self, state_code: str) -> str:
        return (f"{state_code}{self.rng.randint(1, 48):02d}"
                f"{self.rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
                f"{self.rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
                f"{self.rng.randint(1000, 9999)}")

    # ------------------------------------------------------------------
    def build_network(self, archetype: dict, index: int) -> list[Actor]:
        """Construct one hierarchical criminal network."""
        network_name = f"{archetype['domain']} Network {index + 1}"
        city, state, code, lat, lon, areas = self.rng.choice(CITIES)
        actors: list[Actor] = []

        def make(role: str, cell: int, gender: str | None = None) -> Actor:
            g = gender or self.rng.choice(["Male", "Male", "Male", "Female"])
            actor = Actor(
                actor_id=self._next_id("ACT"),
                name=self._name(g),
                alias=self.rng.choice(ALIASES) if self.rng.random() < 0.35 else None,
                role=role, network=network_name, cell=cell,
                age=self.rng.randint(35, 58) if role == "kingpin" else self.rng.randint(21, 45),
                gender=g,
                city=city, state=state,
                phone=self._phone(),
            )
            if role in ("kingpin", "lieutenant", "mule", "financier"):
                actor.account = self._account()
                actor.bank = self.rng.choice(BANKS)
            if role in ("courier", "operative") and self.rng.random() < 0.6:
                actor.vehicle = self._plate(code)
            return actor

        # --- hierarchy ---
        kingpin = make("kingpin", cell=0)
        actors.append(kingpin)

        lieutenants: list[Actor] = []
        for cell in range(archetype["cells"]):
            lt = make("lieutenant", cell=cell + 1)
            lt.reports_to = kingpin.actor_id
            # Kingpin talks ONLY to lieutenants — this is the whole point.
            kingpin.contacts.add(lt.actor_id)
            lt.contacts.add(kingpin.actor_id)
            lieutenants.append(lt)
            actors.append(lt)

        for lt in lieutenants:
            lo, hi = archetype["operatives_per_cell"]
            for _ in range(self.rng.randint(lo, hi)):
                op = make("operative", cell=lt.cell)
                op.reports_to = lt.actor_id
                op.contacts.add(lt.actor_id)
                lt.contacts.add(op.actor_id)
                actors.append(op)
                # Operatives within the same cell sometimes know each other.
                for peer in actors:
                    if (peer.role == "operative" and peer.cell == op.cell
                            and peer.actor_id != op.actor_id and self.rng.random() < 0.45):
                        op.contacts.add(peer.actor_id)
                        peer.contacts.add(op.actor_id)

        # Couriers: deliberately high-volume decoys. They contact many operatives
        # across cells, so degree-based methods will wrongly rank them at the top.
        for _ in range(self.rng.randint(1, 2)):
            courier = make("courier", cell=self.rng.randint(1, archetype["cells"]))
            courier.reports_to = self.rng.choice(lieutenants).actor_id
            operatives = [a for a in actors if a.role == "operative"]
            for op in self.rng.sample(operatives, min(len(operatives), self.rng.randint(4, 7))):
                courier.contacts.add(op.actor_id)
                op.contacts.add(courier.actor_id)
            for lt in lieutenants:
                courier.contacts.add(lt.actor_id)
                lt.contacts.add(courier.actor_id)
            actors.append(courier)

        # Mules: high transaction volume, low social centrality.
        for _ in range(self.rng.randint(2, 3)):
            mule = make("mule", cell=self.rng.randint(1, archetype["cells"]))
            handler = self.rng.choice(lieutenants)
            mule.reports_to = handler.actor_id
            mule.contacts.add(handler.actor_id)
            handler.contacts.add(mule.actor_id)
            actors.append(mule)

        # Peripheral actors: witnesses/associates with one weak link.
        for _ in range(self.rng.randint(2, 4)):
            per = make("peripheral", cell=self.rng.randint(1, archetype["cells"]))
            link = self.rng.choice([a for a in actors if a.role in ("operative", "courier")])
            per.contacts.add(link.actor_id)
            link.contacts.add(per.actor_id)
            actors.append(per)

        return actors

    # ------------------------------------------------------------------
    def generate(self, networks: int = 6) -> Corpus:
        corpus = Corpus()
        all_actors: list[Actor] = []

        for i in range(networks):
            archetype = ARCHETYPES[i % len(ARCHETYPES)]
            actors = self.build_network(archetype, i)
            all_actors.extend(actors)
            corpus.firs.extend(self._make_firs(actors, archetype))
            corpus.cdr.extend(self._make_cdr(actors))
            corpus.transactions.extend(self._make_transactions(actors, archetype))

        # Cross-network bridges: two kingpins linked through a shared facilitator.
        kingpins = [a for a in all_actors if a.role == "kingpin"]
        for a, b in zip(kingpins, kingpins[1:]):
            if self.rng.random() < 0.5:
                bridge = self.rng.choice(
                    [x for x in all_actors if x.network == a.network and x.role == "lieutenant"])
                bridge.contacts.add(b.actor_id)
                b.contacts.add(bridge.actor_id)
                corpus.cdr.extend(self._calls_between(bridge, b, count=self.rng.randint(2, 4)))

        corpus.actors = all_actors
        # Ground truth is restricted to actors who are actually *observable* in
        # the emitted records. An actor who appears in no FIR, CDR or ledger entry
        # cannot be identified by any system, so including them would understate
        # recall against a target that does not exist in the input.
        named_in_firs: set[str] = set()
        for fir in corpus.firs:
            for accused in fir.get("accused", []) or []:
                if accused.get("phone"):
                    named_in_firs.add(accused["phone"])
        corpus.ground_truth = [
            {"entity_name": a.name, "true_role": a.role, "network": a.network,
             "phone": a.phone}
            for a in all_actors if a.phone in named_in_firs
        ]
        return corpus

    # ------------------------------------------------------------------
    def _make_firs(self, actors: list[Actor], archetype: dict) -> list[dict]:
        """
        Emit FIRs. Critically, leadership is under-represented: kingpins appear in
        ~25% of their network's FIRs and usually only as a mentioned name, which
        mirrors reality and makes the detection problem non-trivial.
        """
        firs: list[dict] = []
        city = actors[0].city
        state = actors[0].state
        code = next(c[2] for c in CITIES if c[0] == city)
        areas = next(c[5] for c in CITIES if c[0] == city)
        kingpin = next(a for a in actors if a.role == "kingpin")
        lieutenants = [a for a in actors if a.role == "lieutenant"]
        verbs = archetype["verbs"]

        base_date = datetime(2024, 1, 1) + timedelta(days=self.rng.randint(0, 120))
        kingpin_named_once = False

        for cell_index, lt in enumerate(lieutenants):
            cell_actors = [a for a in actors
                           if a.cell == lt.cell and a.role in ("operative", "courier", "mule")]
            if not cell_actors:
                continue
            for _ in range(self.rng.randint(1, 2)):
                date_filed = base_date + timedelta(days=self.rng.randint(0, 240))
                accused = self.rng.sample(cell_actors, min(len(cell_actors), self.rng.randint(2, 3)))
                accused = [lt] + accused
                # Leadership is under-represented, but intelligence inputs name the
                # kingpin at least once per network — otherwise no system could
                # identify them and the evaluation would be measuring nothing.
                is_last_chance = (cell_index == len(lieutenants) - 1) and not kingpin_named_once
                include_kingpin = is_last_chance or self.rng.random() < 0.25
                if include_kingpin:
                    kingpin_named_once = True
                sections = self.rng.sample(archetype["sections"],
                                           min(len(archetype["sections"]), self.rng.randint(2, 4)))
                area = self.rng.choice(areas)

                narrative = self._narrative(
                    archetype, kingpin, lt, accused, area, city,
                    include_kingpin=include_kingpin, verbs=verbs)

                complainant_gender = "Female" if archetype.get("women_safety") else \
                    self.rng.choice(["Male", "Female"])
                firs.append({
                    "fir_id": f"FIR-2024-{code}-{self.rng.randint(10000, 99999)}",
                    "station": f"{area} Police Station",
                    "district": city,
                    "state": state,
                    "date_filed": date_filed.date().isoformat(),
                    "ipc_sections": sections,
                    "crime_type": archetype["domain"],
                    "priority": self.rng.choice(["High", "High", "Critical", "Medium"]),
                    "status": self.rng.choice(
                        ["Under Investigation", "Under Investigation",
                         "Charge Sheet Filed", "Arrested"]),
                    "investigating_officer": f"Inspector {self._name('Male')}",
                    "complainant": {
                        "name": self._name(complainant_gender),
                        "phone": self._phone(),
                        "address": f"{self.rng.randint(1, 200)}, {area}, {city}",
                        "gender": complainant_gender,
                    },
                    # Names are written as a real record-keeper would: some entries
                    # carry honorifics, initials or transliteration variants. Entity
                    # resolution has to collapse these, which is the whole point.
                    "accused": [
                        {"name": self._name_variant(a), "alias": a.alias, "phone": a.phone,
                         "age": a.age, "gender": a.gender}
                        for a in accused
                    ] + ([{"name": self._name_variant(kingpin), "alias": kingpin.alias,
                           "phone": kingpin.phone, "age": kingpin.age,
                           "gender": kingpin.gender}] if include_kingpin else []),
                    "vehicles_involved": [a.vehicle for a in accused if a.vehicle],
                    "locations_mentioned": self.rng.sample(areas, min(len(areas), 3)),
                    "description": narrative,
                })
        return firs

    def _name_variant(self, actor: Actor) -> str:
        """
        Produce a realistic recording variant of the actor's name.

        Real FIR data is entered by hand across stations, so the same person is
        recorded as 'Vikram Desai', 'Shri Vikram Desai', 'Vikram  Desai.' and
        'V. Desai'. The resolver must reconcile these using the shared phone
        number as corroboration.
        """
        name = actor.name
        roll = self.rng.random()
        if roll < 0.62:
            return name
        parts = name.split()
        if len(parts) < 2:
            return name
        if roll < 0.72:
            return f"{self.rng.choice(['Shri', 'Mr.', 'Md.'])} {name}"
        if roll < 0.80:
            return f"{parts[0]} {parts[-1]}."
        if roll < 0.88:
            return f"{parts[0][0]}. {parts[-1]}"
        if roll < 0.94:
            # Transliteration variance: doubled vowels, s/sh, v/w swaps.
            mutated = parts[0]
            for a, b in (("aa", "a"), ("sh", "s"), ("v", "w"), ("ee", "i")):
                if a in mutated.lower():
                    mutated = mutated.lower().replace(a, b).capitalize()
                    break
            else:
                mutated = mutated + mutated[-1]
            return f"{mutated} {parts[-1]}"
        return f"{name.upper()}"

    def _narrative(self, archetype: dict, kingpin: Actor, lt: Actor,
                   accused: list[Actor], area: str, city: str,
                   include_kingpin: bool, verbs: dict) -> str:
        """
        Build FIR prose that reads like a real police narrative and embeds the
        identifiers the extractor must recover: phones, plates, accounts, amounts.
        """
        parts: list[str] = []
        amount = self.rng.choice([250000, 450000, 850000, 1500000, 2500000, 8500000])
        parts.append(
            f"Complaint pertains to an organised {archetype['domain'].lower()} "
            f"operation active in {area}, {city}."
        )
        parts.append(
            f"Accused {lt.name}"
            + (f" (alias {lt.alias})" if lt.alias else "")
            + f", mobile {lt.phone}, {verbs['lieutenant']} {area}, and coordinates "
            f"the local cell."
        )
        for a in accused:
            if a.actor_id == lt.actor_id:
                continue
            role_verb = verbs.get(a.role, "assists the network in")
            sentence = (f"Co-accused {a.name}"
                        + (f" alias {a.alias}" if a.alias else "")
                        + f" ({a.phone}) {role_verb} {self.rng.choice([area, city])}")
            if a.vehicle:
                sentence += f", using vehicle {a.vehicle}"
            if a.account:
                sentence += f", and operates account no. {a.account} at {a.bank}"
            parts.append(sentence + ".")

        if include_kingpin:
            parts.append(
                f"Interrogation indicates that {kingpin.name}"
                + (f", known as {kingpin.alias}," if kingpin.alias else "")
                + f" {verbs['kingpin']} {kingpin.city} and issues instructions through "
                f"{lt.name}. {kingpin.name} was not present at the scene and is "
                f"reported to avoid direct contact with field operatives."
            )
        else:
            parts.append(
                f"Accused {lt.name} stated that instructions are received from a "
                f"superior whose identity is not disclosed to cell members."
            )

        parts.append(
            f"Total proceeds identified so far amount to Rs {amount:,} transferred "
            f"through multiple accounts."
        )
        parts.append(
            f"Call records show frequent communication between the accused in the "
            f"72 hours preceding the incident. Sections "
            f"{', '.join(archetype['sections'][:3])} have been invoked."
        )
        return " ".join(parts)

    # ------------------------------------------------------------------
    def _make_cdr(self, actors: list[Actor]) -> list[dict]:
        records: list[dict] = []
        by_id = {a.actor_id: a for a in actors}
        # Volume by role: couriers/operatives chatter, kingpins are quiet.
        volume = {"kingpin": (2, 4), "lieutenant": (5, 9), "operative": (6, 12),
                  "courier": (10, 18), "mule": (2, 4), "peripheral": (1, 3)}
        seen: set[tuple[str, str]] = set()
        for actor in actors:
            for contact_id in sorted(actor.contacts):
                pair = tuple(sorted((actor.actor_id, contact_id)))
                if pair in seen:
                    continue
                seen.add(pair)
                other = by_id.get(contact_id)
                if other is None:
                    continue
                lo, hi = volume.get(actor.role, (2, 5))
                lo2, hi2 = volume.get(other.role, (2, 5))
                count = self.rng.randint(min(lo, lo2), max(hi, hi2) // 2 + 1)
                records.extend(self._calls_between(actor, other, count))
        return records

    def _calls_between(self, a: Actor, b: Actor, count: int) -> list[dict]:
        city_info = next((c for c in CITIES if c[0] == a.city), CITIES[0])
        _, _, code, lat, lon, areas = city_info
        out: list[dict] = []
        for _ in range(max(1, count)):
            day = datetime(2024, 1, 1) + timedelta(days=self.rng.randint(0, 300))
            # Leadership calls cluster at odd hours; operatives during the day.
            if a.role in ("kingpin", "lieutenant") or b.role in ("kingpin", "lieutenant"):
                hour = self.rng.choice([23, 0, 1, 2, 4, 22, 21, 11, 15])
            else:
                hour = self.rng.randint(7, 22)
            ts = day.replace(hour=hour, minute=self.rng.randint(0, 59),
                             second=self.rng.randint(0, 59))
            caller, callee = (a, b) if self.rng.random() < 0.5 else (b, a)
            area = self.rng.choice(areas)
            out.append({
                "call_id": self._next_id("CDR"),
                "caller": caller.phone,
                "callee": callee.phone,
                "ts": ts.isoformat(sep=" "),
                "duration": self.rng.randint(20, 900),
                "call_type": self.rng.choice(["voice", "voice", "voice", "sms"]),
                "tower_id": f"{code}-T-{self.rng.randint(1, 400):04d}",
                "tower_name": f"{area} {a.city}",
                "lat": round(lat + self.rng.uniform(-0.12, 0.12), 6),
                "lon": round(lon + self.rng.uniform(-0.12, 0.12), 6),
            })
        return out

    # ------------------------------------------------------------------
    def _make_transactions(self, actors: list[Actor], archetype: dict) -> list[dict]:
        """
        Money mechanics: proceeds are collected by operatives, pass up through
        mules (fan-in), get layered across lieutenant accounts, and part is
        structured just under the CTR threshold before cash extraction.
        """
        txns: list[dict] = []
        kingpin = next(a for a in actors if a.role == "kingpin")
        lieutenants = [a for a in actors if a.role == "lieutenant" and a.account]
        mules = [a for a in actors if a.role == "mule" and a.account]
        if not mules or not lieutenants:
            return txns

        base = datetime(2024, 2, 1)

        def add(frm: Actor | str, to: Actor | str, amount: float, ts: datetime,
                ttype: str, desc: str, flagged: bool) -> None:
            def acct(x: Any) -> tuple[str, str, str]:
                if isinstance(x, str):
                    return x, "CASH", x
                return x.account or "CASH", x.bank or "CASH", x.name
            fa, fb, fn = acct(frm)
            ta, tb, tn = acct(to)
            txns.append({
                "txn_id": self._next_id("TXN"),
                "ts": ts.isoformat(sep=" "),
                "from_account": fa, "from_bank": fb, "from_name": fn,
                "to_account": ta, "to_bank": tb, "to_name": tn,
                "amount": float(amount), "txn_type": ttype,
                "description": desc, "flagged": 1 if flagged else 0,
            })

        # 1. Fan-in: multiple mules feed each lieutenant (collection).
        for lt in lieutenants:
            for mule in mules:
                for _ in range(self.rng.randint(1, 3)):
                    ts = base + timedelta(days=self.rng.randint(0, 200),
                                          hours=self.rng.randint(9, 20))
                    add(mule, lt, self.rng.randint(80000, 600000), ts, "NEFT",
                        "Consolidated collection", True)

        # 2. Structuring: lieutenant slices transfers just under Rs 10 lakh.
        for lt in lieutenants:
            if self.rng.random() < 0.7:
                start = base + timedelta(days=self.rng.randint(30, 180))
                for i in range(self.rng.randint(3, 5)):
                    add(lt, kingpin if kingpin.account else lt,
                        self.rng.randint(930000, 998000),
                        start + timedelta(days=i, hours=self.rng.randint(9, 18)),
                        "RTGS", "Business settlement", True)

        # 3. Layering: value moves lieutenant → lieutenant → kingpin quickly.
        if len(lieutenants) >= 2 and kingpin.account:
            for _ in range(self.rng.randint(1, 3)):
                a, b = self.rng.sample(lieutenants, 2)
                t0 = base + timedelta(days=self.rng.randint(20, 200))
                amount = self.rng.randint(1200000, 4000000)
                add(a, b, amount, t0, "RTGS", "Inter-firm transfer", True)
                add(b, kingpin, amount * self.rng.uniform(0.85, 0.97),
                    t0 + timedelta(hours=self.rng.randint(4, 40)), "RTGS",
                    "Advance against contract", True)

        # 4. Cash extraction by couriers (terminates the trail).
        couriers = [a for a in actors if a.role == "courier"]
        for lt in lieutenants:
            for _ in range(self.rng.randint(1, 3)):
                courier = self.rng.choice(couriers) if couriers else lt
                add(lt, courier.name if not courier.account else courier,
                    self.rng.randint(150000, 900000),
                    base + timedelta(days=self.rng.randint(10, 220)),
                    "ATM", "Cash withdrawal", True)

        # 5. Round-tripping for the economic-offence archetype.
        if archetype["domain"] == "Economic Offence" and len(lieutenants) >= 2 and kingpin.account:
            a, b = lieutenants[0], lieutenants[1]
            t0 = base + timedelta(days=self.rng.randint(40, 160))
            amount = self.rng.randint(2000000, 6000000)
            add(kingpin, a, amount, t0, "RTGS", "Project advance", True)
            add(a, b, amount * 0.98, t0 + timedelta(days=2), "RTGS", "Sub-contract payment", True)
            add(b, kingpin, amount * 0.95, t0 + timedelta(days=4), "RTGS", "Refund of advance", True)

        # 6. Legitimate-looking noise so detectors must discriminate.
        for actor in actors:
            if actor.account and self.rng.random() < 0.5:
                for _ in range(self.rng.randint(1, 3)):
                    add(actor, self._account(), self.rng.randint(2000, 45000),
                        base + timedelta(days=self.rng.randint(0, 300)),
                        self.rng.choice(["UPI", "NEFT", "IMPS"]),
                        self.rng.choice(["Rent", "Utility payment", "Salary",
                                         "Grocery", "Insurance premium"]), False)
        return txns


def generate_corpus(networks: int = 6, seed: int = 20260828) -> Corpus:
    return CorpusGenerator(seed=seed).generate(networks=networks)
