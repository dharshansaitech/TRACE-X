"""
demo/agents/travel_bot.py
A complete, fully-instrumented travel booking agent demo for TRACE-X.

This agent handles natural-language travel requests end-to-end:
  1. Parse user intent (destination, dates, passengers)
  2. Search flights via mock tool
  3. Fetch hotel options via mock tool
  4. Price lookup and availability check
  5. Generate a booking recommendation

Run it:
    python demo/agents/travel_bot.py
    python demo/agents/travel_bot.py --inject tool_failure
    python demo/agents/travel_bot.py --inject stale_data
    python demo/agents/travel_bot.py --inject hallucination
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Any

# ── SDK bootstrap ─────────────────────────────────────────────────────────────
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk"))

try:
    import tracex

    TRACEX_AVAILABLE = True
except ImportError:
    TRACEX_AVAILABLE = False
    print("⚠  tracex SDK not found — running without instrumentation")

BACKEND_URL = os.environ.get("TRACEX_BACKEND_URL", "http://localhost:8000")
API_KEY = os.environ.get("TRACEX_API_KEY", "dev-key")

# ─────────────────────────────────────────────────────────────────────────────
# Mock tool implementations
# ─────────────────────────────────────────────────────────────────────────────

MOCK_FLIGHTS = [
    {"flight_id": "AA101", "origin": "JFK", "destination": "LAX", "price": 299.00, "duration_min": 340, "seats": 12},
    {"flight_id": "DL202", "origin": "JFK", "destination": "LAX", "price": 315.00, "duration_min": 355, "seats": 6},
    {"flight_id": "UA303", "origin": "JFK", "destination": "LAX", "price": 289.00, "duration_min": 360, "seats": 0},
    {"flight_id": "SW404", "origin": "JFK", "destination": "LAX", "price": 249.00, "duration_min": 400, "seats": 30},
]

MOCK_HOTELS = [
    {"hotel_id": "H001", "name": "The Grand LAX", "stars": 5, "price_per_night": 289.00, "available_rooms": 3},
    {"hotel_id": "H002", "name": "Sunset Boutique", "stars": 4, "price_per_night": 189.00, "available_rooms": 8},
    {"hotel_id": "H003", "name": "Budget Inn Express", "stars": 2, "price_per_night": 79.00, "available_rooms": 20},
]

MOCK_WEATHER = {
    "LAX": {"forecast": "Sunny, 75°F", "rain_probability": 0.05},
    "JFK": {"forecast": "Partly cloudy, 62°F", "rain_probability": 0.20},
    "ORD": {"forecast": "Rainy, 55°F", "rain_probability": 0.70},
}


class ToolFailureError(Exception):
    pass


async def tool_search_flights(
    origin: str,
    destination: str,
    date: str,
    passengers: int,
    inject_failure: str = "",
) -> dict[str, Any]:
    """Mock flight search tool."""
    await asyncio.sleep(0.3)

    if inject_failure == "tool_failure" and random.random() > 0.3:
        raise ToolFailureError("Flight API timeout: upstream provider returned 503")

    flights = [
        f for f in MOCK_FLIGHTS
        if f["origin"] == origin.upper() and f["destination"] == destination.upper()
        if f["seats"] >= passengers
    ]

    if inject_failure == "stale_data":
        # Return data with a suspiciously old timestamp
        for f in flights:
            f["price"] = f["price"] * 0.5  # Prices from 6 months ago
        return {
            "flights": flights,
            "data_timestamp": (datetime.utcnow() - timedelta(days=180)).isoformat(),
            "currency": "USD",
        }

    return {
        "flights": flights,
        "data_timestamp": datetime.utcnow().isoformat(),
        "currency": "USD",
    }


async def tool_search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    inject_failure: str = "",
) -> dict[str, Any]:
    """Mock hotel search tool."""
    await asyncio.sleep(0.2)

    if inject_failure == "tool_failure" and random.random() > 0.5:
        raise ToolFailureError("Hotel API error: invalid API credentials")

    hotels = [h for h in MOCK_HOTELS if h["available_rooms"] >= 1]

    return {
        "hotels": hotels,
        "check_in": check_in,
        "check_out": check_out,
        "currency": "USD",
    }


async def tool_get_weather(location: str) -> dict[str, Any]:
    """Mock weather tool."""
    await asyncio.sleep(0.1)
    return MOCK_WEATHER.get(location.upper(), {"forecast": "Unknown", "rain_probability": 0.0})


async def tool_check_availability(flight_id: str, hotel_id: str) -> dict[str, Any]:
    """Mock final availability check tool."""
    await asyncio.sleep(0.15)
    flight = next((f for f in MOCK_FLIGHTS if f["flight_id"] == flight_id), None)
    hotel = next((h for h in MOCK_HOTELS if h["hotel_id"] == hotel_id), None)

    if not flight or not hotel:
        return {"available": False, "reason": "Resource not found"}

    return {
        "available": flight["seats"] > 0 and hotel["available_rooms"] > 0,
        "flight_confirmed": flight["seats"] > 0,
        "hotel_confirmed": hotel["available_rooms"] > 0,
        "booking_window_hours": 24,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LLM mock (simulates Gemini calls without real API key)
# ─────────────────────────────────────────────────────────────────────────────

async def llm_parse_intent(user_message: str) -> dict[str, Any]:
    """Parse travel intent from natural language (mocked)."""
    await asyncio.sleep(0.4)

    # Simulate structured extraction
    intent = {
        "origin": "JFK",
        "destination": "LAX",
        "departure_date": (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d"),
        "return_date": (datetime.utcnow() + timedelta(days=21)).strftime("%Y-%m-%d"),
        "passengers": 2,
        "trip_type": "round_trip",
        "budget_per_person": 500.0,
        "preferences": ["direct_flight", "mid_range_hotel"],
    }

    return intent


async def llm_generate_recommendation(
    intent: dict,
    flights: list,
    hotels: list,
    weather: dict,
    inject_hallucination: bool = False,
) -> str:
    """Generate a booking recommendation (mocked LLM response)."""
    await asyncio.sleep(0.6)

    if inject_hallucination:
        # Hallucination: recommends a flight that doesn't exist
        return (
            "I recommend booking flight XY999 operated by SkyBridge Airlines "
            "for $189 per person — this is their new direct service launched last month. "
            "Pair it with The Grand LAX hotel at $289/night for a premium experience. "
            "Total estimated cost: $578 per person for 7 nights. "
            "Note: SkyBridge offers complimentary lounge access for all bookings."
        )

    if not flights:
        return "No available flights found for your dates. Please consider alternate dates or nearby airports."

    best_flight = min(flights, key=lambda f: f["price"])
    best_hotel = min(hotels, key=lambda h: h["price_per_night"])

    nights = 7
    total = (best_flight["price"] * intent["passengers"]) + (best_hotel["price_per_night"] * nights)

    return (
        f"I recommend flight {best_flight['flight_id']} at ${best_flight['price']:.2f}/person "
        f"({best_flight['duration_min'] // 60}h {best_flight['duration_min'] % 60}m). "
        f"For accommodation, {best_hotel['name']} ({best_hotel['stars']}★) at "
        f"${best_hotel['price_per_night']:.2f}/night works well. "
        f"Estimated total: ${total:.2f} for {intent['passengers']} passengers, {nights} nights. "
        f"Weather in {intent['destination']}: {weather.get('forecast', 'N/A')}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main agent
# ─────────────────────────────────────────────────────────────────────────────

class TravelBookingAgent:
    """
    End-to-end travel booking agent, fully instrumented with TRACE-X SDK.
    """

    def __init__(self, inject_failure: str = ""):
        self.inject_failure = inject_failure
        self.agent_id = "travel-bot-v1"

    async def run(self, user_message: str) -> str:
        """
        Process a travel booking request.
        Returns a booking recommendation string.
        """
        if TRACEX_AVAILABLE:
            return await self._run_instrumented(user_message)
        else:
            return await self._run_core(user_message)

    async def _run_instrumented(self, user_message: str) -> str:
        """Run with full TRACE-X instrumentation."""
        async with tracex.trace(
            name="travel_booking_request",
            agent_id=self.agent_id,
            metadata={"user_message": user_message, "inject_failure": self.inject_failure},
        ) as span:
            span.set_input({"message": user_message})

            try:
                result = await self._run_core(user_message, parent_span=span)
                span.set_output({"recommendation": result[:200]})
                return result
            except Exception as exc:
                span.set_error(str(exc), type(exc).__name__)
                raise

    async def _run_core(self, user_message: str, parent_span: Any = None) -> str:
        """Core agent logic."""

        # ── Step 1: Parse intent ───────────────────────────────────────────────
        print(f"\n[Step 1] Parsing intent from: '{user_message}'")

        if TRACEX_AVAILABLE and parent_span:
            tc = parent_span.start_tool_call(
                tool_name="llm_parse_intent",
                tool_input={"message": user_message},
            )

        intent = await llm_parse_intent(user_message)

        if TRACEX_AVAILABLE and parent_span:
            parent_span.finish_tool_call(
                tc,
                output=intent,
                latency_ms=400,
                model="gemini-2.0-flash-001",
                tokens_used={"prompt": 150, "completion": 80},
            )

        print(f"   Intent: {intent['origin']} → {intent['destination']}, {intent['passengers']} pax")

        # ── Step 2: Search flights ─────────────────────────────────────────────
        print(f"\n[Step 2] Searching flights...")

        if TRACEX_AVAILABLE and parent_span:
            tc_flights = parent_span.start_tool_call(
                tool_name="search_flights",
                tool_input={
                    "origin": intent["origin"],
                    "destination": intent["destination"],
                    "date": intent["departure_date"],
                    "passengers": intent["passengers"],
                },
            )

        try:
            t0 = time.monotonic()
            flight_results = await tool_search_flights(
                origin=intent["origin"],
                destination=intent["destination"],
                date=intent["departure_date"],
                passengers=intent["passengers"],
                inject_failure=self.inject_failure,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            flights = flight_results["flights"]
            print(f"   Found {len(flights)} flights")

            if TRACEX_AVAILABLE and parent_span:
                parent_span.finish_tool_call(tc_flights, output=flight_results, latency_ms=latency_ms)

        except ToolFailureError as exc:
            print(f"   TOOL FAILURE: {exc}")
            if TRACEX_AVAILABLE and parent_span:
                parent_span.finish_tool_call(tc_flights, error=str(exc), latency_ms=300.0)
            # Retry once with empty result
            flights = []

        # ── Step 3: Search hotels ──────────────────────────────────────────────
        print(f"\n[Step 3] Searching hotels in {intent['destination']}...")

        if TRACEX_AVAILABLE and parent_span:
            tc_hotels = parent_span.start_tool_call(
                tool_name="search_hotels",
                tool_input={
                    "location": intent["destination"],
                    "check_in": intent["departure_date"],
                    "check_out": intent["return_date"],
                    "guests": intent["passengers"],
                },
            )

        try:
            t0 = time.monotonic()
            hotel_results = await tool_search_hotels(
                location=intent["destination"],
                check_in=intent["departure_date"],
                check_out=intent["return_date"],
                guests=intent["passengers"],
                inject_failure=self.inject_failure,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            hotels = hotel_results["hotels"]
            print(f"   Found {len(hotels)} hotels")

            if TRACEX_AVAILABLE and parent_span:
                parent_span.finish_tool_call(tc_hotels, output=hotel_results, latency_ms=latency_ms)

        except ToolFailureError as exc:
            print(f"   TOOL FAILURE: {exc}")
            if TRACEX_AVAILABLE and parent_span:
                parent_span.finish_tool_call(tc_hotels, error=str(exc), latency_ms=200.0)
            hotels = []

        # ── Step 4: Get weather ────────────────────────────────────────────────
        print(f"\n[Step 4] Fetching weather for {intent['destination']}...")

        if TRACEX_AVAILABLE and parent_span:
            tc_weather = parent_span.start_tool_call(
                tool_name="get_weather",
                tool_input={"location": intent["destination"]},
            )

        t0 = time.monotonic()
        weather = await tool_get_weather(intent["destination"])
        latency_ms = (time.monotonic() - t0) * 1000

        print(f"   Weather: {weather.get('forecast', 'N/A')}")

        if TRACEX_AVAILABLE and parent_span:
            parent_span.finish_tool_call(tc_weather, output=weather, latency_ms=latency_ms)

        # ── Step 5: Availability check ─────────────────────────────────────────
        if flights and hotels:
            best_flight = min(flights, key=lambda f: f["price"])
            best_hotel = min(hotels, key=lambda h: h["price_per_night"])

            print(f"\n[Step 5] Checking availability for {best_flight['flight_id']} + {best_hotel['hotel_id']}...")

            if TRACEX_AVAILABLE and parent_span:
                tc_avail = parent_span.start_tool_call(
                    tool_name="check_availability",
                    tool_input={"flight_id": best_flight["flight_id"], "hotel_id": best_hotel["hotel_id"]},
                )

            t0 = time.monotonic()
            availability = await tool_check_availability(best_flight["flight_id"], best_hotel["hotel_id"])
            latency_ms = (time.monotonic() - t0) * 1000

            print(f"   Available: {availability['available']}")

            if TRACEX_AVAILABLE and parent_span:
                parent_span.finish_tool_call(tc_avail, output=availability, latency_ms=latency_ms)
        else:
            availability = {"available": False}

        # ── Step 6: Generate recommendation ───────────────────────────────────
        print(f"\n[Step 6] Generating recommendation...")

        if TRACEX_AVAILABLE and parent_span:
            tc_rec = parent_span.start_tool_call(
                tool_name="llm_generate_recommendation",
                tool_input={"intent": intent, "flights_count": len(flights), "hotels_count": len(hotels)},
            )

        inject_hallucination = self.inject_failure == "hallucination"

        t0 = time.monotonic()
        recommendation = await llm_generate_recommendation(
            intent=intent,
            flights=flights,
            hotels=hotels,
            weather=weather,
            inject_hallucination=inject_hallucination,
        )
        latency_ms = (time.monotonic() - t0) * 1000

        if TRACEX_AVAILABLE and parent_span:
            parent_span.finish_tool_call(
                tc_rec,
                output={"recommendation": recommendation[:200]},
                latency_ms=latency_ms,
                model="gemini-2.0-flash-001",
                tokens_used={"prompt": 400, "completion": 150},
            )

        return recommendation


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="TRACE-X Travel Bot Demo")
    parser.add_argument(
        "--inject",
        choices=["", "tool_failure", "stale_data", "hallucination"],
        default="",
        help="Failure mode to inject",
    )
    parser.add_argument(
        "--message",
        default="Book me a round-trip from JFK to LAX for 2 passengers next month, mid-range budget",
        help="Travel request message",
    )
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    args = parser.parse_args()

    if TRACEX_AVAILABLE:
        tracex.init(
            backend_url=BACKEND_URL,
            api_key=API_KEY,
            agent_id="travel-bot-v1",
            debug=True,
        )
        print(f"✓ TRACE-X SDK initialized → {BACKEND_URL}")
    else:
        print("⚠  Running without TRACE-X (SDK not available)")

    print("\n" + "━" * 60)
    print("  TRACE-X Travel Bot Demo")
    print(f"  Failure injection: {args.inject or 'none'}")
    print("━" * 60)

    agent = TravelBookingAgent(inject_failure=args.inject)

    for i in range(args.runs):
        if args.runs > 1:
            print(f"\n{'─'*40}")
            print(f"  Run {i+1}/{args.runs}")
            print(f"{'─'*40}")

        try:
            result = await agent.run(args.message)
            print(f"\n{'='*60}")
            print("  RECOMMENDATION:")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}\n")
        except Exception as exc:
            print(f"\n  ERROR: {exc}\n")

        if args.runs > 1 and i < args.runs - 1:
            await asyncio.sleep(0.5)

    if TRACEX_AVAILABLE:
        await tracex.flush()
        print("\n✓ Traces flushed to TRACE-X backend")


if __name__ == "__main__":
    asyncio.run(main())
