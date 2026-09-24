"""
Graph Schema Definitions
Node and Edge data representations for the Criminal Network
"""

from typing import Dict, List, Any, Optional
import hashlib
from datetime import datetime, timezone

def hash_identifier(value: str) -> str:
    """Helper to create deterministic ID hash for entity resolution and PII masking."""
    clean_val = "".join(filter(str.isalnum, str(value).upper()))
    return hashlib.sha256(clean_val.encode()).hexdigest()[:16]

class Node:
    """Represents a vertex in the multi-relational criminal graph."""
    def __init__(
        self,
        node_id: str,
        label: str,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.node_id = str(node_id)
        self.label = label  # Person, Case, Organization, Location, CommunicationRecord, FinancialAccount, Vehicle
        self.name = name
        self.attributes = attributes or {}
        if "created_at" not in self.attributes:
            self.attributes["created_at"] = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node_id,
            "label": self.label,
            "name": self.name,
            **self.attributes
        }


class Edge:
    """Represents a relationship edge connecting two entities in the network."""
    def __init__(
        self,
        edge_id: str,
        source: str,
        target: str,
        relation_type: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.edge_id = str(edge_id)
        self.source = str(source)
        self.target = str(target)
        self.relation_type = relation_type  # ASSOCIATE_OF, ACCUSED_IN, MEMBER_OF, CONTACTED, etc.
        self.attributes = attributes or {}
        if "weight" not in self.attributes:
            self.attributes["weight"] = 1.0
        if "created_at" not in self.attributes:
            self.attributes["created_at"] = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            **self.attributes
        }
