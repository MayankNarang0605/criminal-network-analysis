"""
Neo4j database connection — adapted from Thxrun's Neo4jDatabase with reconnect/health.
"""
import time
from typing import Any, Dict, List, Optional

import neo4j
from neo4j import GraphDatabase, Driver, Session
from backend.config import settings
from backend.logging_config import logger


class Neo4jDatabase:
    """Thread-safe Neo4j driver wrapper with health check and auto-reconnect."""

    def __init__(self):
        self._driver: Optional[Driver] = None

    def connect(self) -> Driver:
        if self._driver is None:
            try:
                driver_kwargs = {
                    "auth": (settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
                    "max_connection_pool_size": settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
                    "connection_timeout": 15.0,
                    "max_connection_lifetime": 180,
                    "keep_alive": True,
                    "liveness_check_timeout": 1.0,
                }
                # Suppress driver-level notifications if supported
                if hasattr(neo4j, "NotificationMinimumSeverity"):
                    driver_kwargs["notifications_min_severity"] = getattr(
                        neo4j, "NotificationMinimumSeverity"
                    ).OFF

                self._driver = GraphDatabase.driver(settings.NEO4J_URI, **driver_kwargs)
                logger.info(f"Connected to Neo4j at {settings.NEO4J_URI}")
            except Exception as exc:
                logger.error(f"Failed to create Neo4j driver: {exc}")
                raise
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None
            logger.info("Neo4j driver closed.")

    def reconnect(self) -> Driver:
        self.close()
        return self.connect()

    def get_session(self, database: Optional[str] = None) -> Session:
        driver = self.connect()
        db = database or settings.NEO4J_DATABASE
        if db and not settings.NEO4J_URI.startswith("neo4j+s://"):
            return driver.session(database=db)
        return driver.session()

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def check_health(self) -> Dict[str, Any]:
        if not self.is_healthy():
            return {
                "status": "offline",
                "database": settings.NEO4J_DATABASE,
                "note": "Neo4j not reachable; database fallback active.",
            }
        start = time.time()
        try:
            with self.get_session() as session:
                result = session.run(
                    "CALL dbms.components() YIELD name, versions, edition "
                    "RETURN name, versions, edition"
                )
                records = list(result)
                record = records[0] if records else None
                latency = round((time.time() - start) * 1000, 2)

                # Check GDS availability
                gds_available = False
                gds_version = None
                if settings.ENABLE_GDS:
                    try:
                        gds_res = session.run("CALL gds.version() YIELD version RETURN version")
                        gds_rec = gds_res.single()
                        if gds_rec:
                            gds_available = True
                            gds_version = gds_rec["version"]
                    except Exception:
                        pass

                return {
                    "status": "healthy",
                    "database": settings.NEO4J_DATABASE,
                    "version": record["versions"][0] if record and record.get("versions") else "unknown",
                    "edition": record["edition"] if record else "community",
                    "gds_available": gds_available,
                    "gds_version": gds_version,
                    "latency_ms": latency,
                }
        except Exception as exc:
            logger.warning(f"Neo4j health check failed ({exc}), attempting reconnect...")
            try:
                self.reconnect()
                return self.check_health()
            except Exception as retry_exc:
                return {
                    "status": "unhealthy",
                    "database": settings.NEO4J_DATABASE,
                    "error": str(retry_exc),
                    "latency_ms": round((time.time() - start) * 1000, 2),
                }

    def is_healthy(self) -> bool:
        """Instant check whether Neo4j Bolt port is reachable."""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            res = sock.connect_ex(('localhost', 7687))
            sock.close()
            return res == 0
        except Exception:
            return False


neo4j_db = Neo4jDatabase()
