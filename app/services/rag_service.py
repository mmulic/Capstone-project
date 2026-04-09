"""
RAG Context Retrieval Service (BE-015)
=======================================
Retrieves relevant property/prediction data for the chatbot.
Two retrieval strategies:
1. Spatial lookup — for address/location queries (PostGIS)
2. Keyword search — for general queries (damage stats, summaries)
"""

import json
from typing import Optional

from sqlalchemy import select, func, and_, or_, desc, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID

from app.models.models import Property, Prediction, Image, DamageClass


class RAGRetrievalService:
    """Retrieves and formats context for LLM consumption."""

    async def retrieve_context(
        self, query: str, db: AsyncSession, max_results: int = 10
    ) -> dict:
        """
        Main retrieval method. Analyzes query type and routes to appropriate strategy.

        Returns:
            {
                "strategy": "spatial" | "keyword" | "stats",
                "results": [...],
                "summary": "...",
                "formatted_context": "..." (text block for LLM)
            }
        """
        query_lower = query.lower().strip()

        # Check if it's a stats/summary query
        if self._is_stats_query(query_lower):
            return await self._retrieve_stats(db)

        # Check if it's a spatial/address query
        address = self._extract_address(query_lower)
        if address:
            return await self._retrieve_by_address(address, db, max_results)

        # Check for damage-level queries
        damage_level = self._extract_damage_level(query_lower)
        if damage_level:
            return await self._retrieve_by_damage(damage_level, db, max_results)

        # Fallback: keyword search across addresses
        return await self._retrieve_by_keyword(query, db, max_results)

    # ── Strategy: Spatial Lookup ─────────────────────────

    async def _retrieve_by_address(
        self, address: str, db: AsyncSession, max_results: int
    ) -> dict:
        """Search properties by address text match."""
        query = (
            select(Property, Prediction)
            .outerjoin(Prediction, and_(
                Property.id == Prediction.property_id,
            ))
            .where(Property.address.ilike(f"%{address}%"))
            .order_by(desc(Prediction.created_at))
            .limit(max_results)
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return {
                "strategy": "spatial",
                "results": [],
                "summary": f"No properties found matching '{address}'",
                "formatted_context": f"No assessment data found for the address or location: {address}",
            }

        records = self._format_property_records(rows)
        return {
            "strategy": "spatial",
            "results": records,
            "summary": f"Found {len(records)} properties matching '{address}'",
            "formatted_context": self._format_for_llm(records),
        }

    async def retrieve_by_coordinates(
        self, lat: float, lng: float, radius_m: float, db: AsyncSession, max_results: int = 10
    ) -> dict:
        """Search properties within radius of coordinates using PostGIS."""
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)

        query = (
            select(Property, Prediction)
            .outerjoin(Prediction, Property.id == Prediction.property_id)
            .where(ST_DWithin(
                Property.location,
                point,
                radius_m / 111320  # approximate degrees
            ))
            .order_by(desc(Prediction.created_at))
            .limit(max_results)
        )

        result = await db.execute(query)
        rows = result.all()

        records = self._format_property_records(rows)
        return {
            "strategy": "spatial",
            "results": records,
            "summary": f"Found {len(records)} properties within {radius_m}m of ({lat}, {lng})",
            "formatted_context": self._format_for_llm(records),
        }

    # ── Strategy: Damage Level Filter ────────────────────

    async def _retrieve_by_damage(
        self, damage_level: DamageClass, db: AsyncSession, max_results: int
    ) -> dict:
        """Retrieve properties filtered by damage classification."""
        query = (
            select(Property, Prediction)
            .join(Prediction, Property.id == Prediction.property_id)
            .where(Prediction.damage_class == damage_level)
            .order_by(desc(Prediction.confidence))
            .limit(max_results)
        )

        result = await db.execute(query)
        rows = result.all()

        records = self._format_property_records(rows)
        return {
            "strategy": "damage_filter",
            "results": records,
            "summary": f"Found {len(records)} properties classified as '{damage_level.value}'",
            "formatted_context": self._format_for_llm(records),
        }

    # ── Strategy: Keyword Search ─────────────────────────

    async def _retrieve_by_keyword(
        self, keyword: str, db: AsyncSession, max_results: int
    ) -> dict:
        """Fallback: search by address, city, or state keywords."""
        search_term = f"%{keyword}%"

        query = (
            select(Property, Prediction)
            .outerjoin(Prediction, Property.id == Prediction.property_id)
            .where(or_(
                Property.address.ilike(search_term),
                Property.city.ilike(search_term),
                Property.state.ilike(search_term),
                Property.external_id.ilike(search_term),
            ))
            .order_by(desc(Prediction.created_at))
            .limit(max_results)
        )

        result = await db.execute(query)
        rows = result.all()

        records = self._format_property_records(rows)
        return {
            "strategy": "keyword",
            "results": records,
            "summary": f"Found {len(records)} properties matching '{keyword}'",
            "formatted_context": self._format_for_llm(records),
        }

    # ── Strategy: Stats / Summary ────────────────────────

    async def _retrieve_stats(self, db: AsyncSession) -> dict:
        """Get overall damage statistics for summary queries."""
        # Total properties
        total_result = await db.execute(select(func.count(Property.id)))
        total_props = total_result.scalar() or 0

        # Total assessed
        assessed_result = await db.execute(
            select(func.count(func.distinct(Prediction.property_id)))
        )
        total_assessed = assessed_result.scalar() or 0

        # Damage distribution
        dist_result = await db.execute(
            select(Prediction.damage_class, func.count(Prediction.id))
            .group_by(Prediction.damage_class)
        )
        distribution = {row[0].value: row[1] for row in dist_result.all()}

        # Average confidence
        avg_result = await db.execute(
            select(func.avg(Prediction.confidence))
        )
        avg_confidence = avg_result.scalar()

        stats = {
            "total_properties": total_props,
            "total_assessed": total_assessed,
            "damage_distribution": distribution,
            "average_confidence": round(avg_confidence, 3) if avg_confidence else None,
        }

        formatted = (
            f"Assessment Statistics:\n"
            f"- Total properties in system: {total_props}\n"
            f"- Properties assessed: {total_assessed}\n"
            f"- Damage distribution: {json.dumps(distribution)}\n"
            f"- Average confidence: {stats['average_confidence']}\n"
        )

        return {
            "strategy": "stats",
            "results": [stats],
            "summary": f"{total_assessed} of {total_props} properties assessed",
            "formatted_context": formatted,
        }

    # ── Query Analysis Helpers ───────────────────────────

    def _is_stats_query(self, query: str) -> bool:
        """Check if query is asking for overall statistics."""
        stats_keywords = [
            "how many", "total", "summary", "summarize", "overview",
            "statistics", "stats", "count", "breakdown", "distribution",
            "overall", "all properties", "entire", "whole area",
        ]
        return any(kw in query for kw in stats_keywords)

    def _extract_address(self, query: str) -> Optional[str]:
        """Try to extract an address from the query."""
        address_prefixes = [
            "damage at ", "assessment for ", "status of ",
            "what is the damage at ", "what's the damage at ",
            "damage on ", "assessment at ", "report for ",
            "check ", "look up ", "find ",
        ]
        for prefix in address_prefixes:
            if prefix in query:
                addr = query.split(prefix, 1)[1].strip().rstrip("?.,!")
                if addr:
                    return addr

        # Check for street-like patterns (numbers + street name)
        words = query.split()
        for i, word in enumerate(words):
            if word.isdigit() and i + 1 < len(words):
                potential_addr = " ".join(words[i:]).rstrip("?.,!")
                if len(potential_addr) > 5:
                    return potential_addr

        return None

    def _extract_damage_level(self, query: str) -> Optional[DamageClass]:
        """Check if query is filtering by damage level."""
        mappings = {
            "destroyed": DamageClass.DESTROYED,
            "major damage": DamageClass.MAJOR,
            "major": DamageClass.MAJOR,
            "minor damage": DamageClass.MINOR,
            "minor": DamageClass.MINOR,
            "no damage": DamageClass.NO_DAMAGE,
            "undamaged": DamageClass.NO_DAMAGE,
        }
        for keyword, level in mappings.items():
            if keyword in query:
                return level
        return None

    # ── Formatting Helpers ───────────────────────────────

    def _format_property_records(self, rows) -> list[dict]:
        """Format DB rows into clean record dicts."""
        seen = set()
        records = []
        for row in rows:
            prop = row[0]
            pred = row[1] if len(row) > 1 else None

            # Deduplicate by property ID
            prop_key = str(prop.id)
            if prop_key in seen:
                continue
            seen.add(prop_key)

            record = {
                "property_id": prop_key,
                "address": prop.address,
                "latitude": prop.latitude,
                "longitude": prop.longitude,
                "city": prop.city,
                "state": prop.state,
            }

            if pred:
                record.update({
                    "damage_class": pred.damage_class.value,
                    "confidence": pred.confidence,
                    "rationale": pred.rationale,
                })
            else:
                record["damage_class"] = "not_assessed"

            records.append(record)

        return records

    def _format_for_llm(self, records: list[dict]) -> str:
        """Format records as a text block for LLM context injection."""
        if not records:
            return "No assessment data found for the requested location or criteria."

        lines = [f"Found {len(records)} relevant property records:\n"]
        for i, rec in enumerate(records, 1):
            addr = rec.get("address") or f"({rec['latitude']}, {rec['longitude']})"
            damage = rec.get("damage_class", "unknown")
            confidence = rec.get("confidence")
            rationale = rec.get("rationale")

            line = f"{i}. {addr} — Damage: {damage}"
            if confidence:
                line += f" (confidence: {confidence:.1%})"
            if rationale:
                line += f"\n   Rationale: {rationale}"
            lines.append(line)

        return "\n".join(lines)


# Singleton
rag_service = RAGRetrievalService()
