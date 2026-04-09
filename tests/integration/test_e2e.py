#!/usr/bin/env python3
"""
End-to-End Integration Test (BE-028)
=====================================
Tests the full pipeline against a deployed environment:
ingest -> predict -> query -> chat -> evaluate

Usage:
    python tests/integration/test_e2e.py http://localhost:8000
    python tests/integration/test_e2e.py https://api.disaster-assessment.example.com
"""

import io
import sys
import time
import asyncio
from pathlib import Path

import httpx
from PIL import Image


def make_test_image(seed: int = 0) -> bytes:
    """Generate a test image with a unique color pattern."""
    img = Image.new("RGB", (256, 256), color=(seed % 255, (seed * 7) % 255, (seed * 13) % 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class E2ETest:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self.passed = 0
        self.failed = 0
        self.property_id = None
        self.session_id = None

    async def close(self):
        await self.client.aclose()

    def _check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            print(f"  ✓ {name}")
            self.passed += 1
        else:
            print(f"  ✗ {name} — {detail}")
            self.failed += 1

    # ── Tests ────────────────────────────────────────────

    async def test_health(self):
        print("\n[1/8] Health check")
        r = await self.client.get("/health")
        self._check("status 200", r.status_code == 200, str(r.status_code))
        self._check("returns healthy", r.json().get("status") == "healthy")

    async def test_swagger(self):
        print("\n[2/8] Swagger UI available")
        r = await self.client.get("/docs")
        self._check("docs accessible", r.status_code == 200)

    async def test_ingest(self):
        print("\n[3/8] Image ingest")
        files = {
            "pre_image": ("pre.jpg", make_test_image(1), "image/jpeg"),
            "post_image": ("post.jpg", make_test_image(2), "image/jpeg"),
        }
        data = {
            "latitude": "29.7604",
            "longitude": "-95.3698",
            "address": "Houston test property",
        }
        r = await self.client.post("/api/ingest", files=files, data=data)
        self._check("ingest 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            self.property_id = body.get("property_id")
            self._check("property_id returned", self.property_id is not None)

    async def test_geojson(self):
        print("\n[4/8] GeoJSON endpoint")
        r = await self.client.get("/api/geojson")
        self._check("geojson 200", r.status_code == 200)
        if r.status_code == 200:
            body = r.json()
            self._check("FeatureCollection format", body.get("type") == "FeatureCollection")
            self._check("contains features", len(body.get("features", [])) > 0)

    async def test_predict(self):
        print("\n[5/8] Trigger prediction")
        if not self.property_id:
            print("  ⊘ skipped (no property_id)")
            return

        r = await self.client.post(
            "/api/predict",
            json={"property_ids": [self.property_id]},
        )
        self._check("predict 200", r.status_code == 200, f"{r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            body = r.json()
            self._check("returns damage_class", "damage_class" in body)
            self._check("confidence in [0,1]", 0.0 <= body.get("confidence", -1) <= 1.0)

    async def test_results(self):
        print("\n[6/8] Query results")
        r = await self.client.get("/api/results?page=1&page_size=10")
        self._check("results 200", r.status_code == 200)
        if r.status_code == 200:
            body = r.json()
            self._check("returns items array", "items" in body)
            self._check("pagination metadata", "total" in body and "page" in body)

    async def test_chat(self):
        print("\n[7/8] Chatbot query")
        r = await self.client.post(
            "/api/chat",
            json={"message": "How many properties were destroyed?"},
        )
        self._check("chat 200", r.status_code == 200, f"{r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            body = r.json()
            self._check("returns response text", isinstance(body.get("response"), str))
            self._check("returns session_id", body.get("session_id") is not None)

    async def test_stats(self):
        print("\n[8/8] Dashboard stats")
        r = await self.client.get("/api/stats")
        self._check("stats 200", r.status_code == 200)
        if r.status_code == 200:
            body = r.json()
            self._check("total_properties >= 0", body.get("total_properties", -1) >= 0)
            self._check("damage_distribution present", "damage_distribution" in body)

    # ── Runner ───────────────────────────────────────────

    async def run(self):
        print(f"\n=== End-to-End Integration Test ===")
        print(f"Target: {self.base_url}\n")

        start = time.time()
        await self.test_health()
        await self.test_swagger()
        await self.test_ingest()
        await self.test_geojson()
        await self.test_predict()
        await self.test_results()
        await self.test_chat()
        await self.test_stats()
        elapsed = time.time() - start

        print(f"\n=== Results ===")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Duration: {elapsed:.2f}s")

        await self.close()
        return self.failed == 0


async def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    test = E2ETest(base_url)
    success = await test.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
