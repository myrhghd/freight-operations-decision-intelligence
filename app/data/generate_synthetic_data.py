from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 42
N_CARRIERS = 10
N_CUSTOMERS = 50
N_ROUTES = 25
N_SHIPMENTS = 1_000

random.seed(SEED)
rng = np.random.default_rng(SEED)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


CARRIER_TYPES = ["FTL", "LTL", "Parcel", "Intermodal", "Drayage"]
CUSTOMER_TIERS = ["Strategic", "Enterprise", "Growth", "Standard"]
INDUSTRIES = [
    "Retail",
    "Manufacturing",
    "Healthcare",
    "Automotive",
    "Consumer Goods",
    "Electronics",
    "Food & Beverage",
]
REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
SHIPMENT_MODES = ["Truckload", "Less-than-truckload", "Parcel", "Rail", "Intermodal"]
LANE_TYPES = ["Regional", "Long-haul", "Cross-border", "Port drayage", "Metro"]
EVENT_TYPES = [
    "CREATED",
    "PICKED_UP",
    "IN_TRANSIT",
    "ARRIVED_AT_HUB",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "DELAYED",
    "CUSTOMS_HOLD",
]

CITY_STATE_PAIRS = [
    ("Atlanta", "GA"),
    ("Austin", "TX"),
    ("Baltimore", "MD"),
    ("Charlotte", "NC"),
    ("Chicago", "IL"),
    ("Columbus", "OH"),
    ("Dallas", "TX"),
    ("Denver", "CO"),
    ("Detroit", "MI"),
    ("Houston", "TX"),
    ("Indianapolis", "IN"),
    ("Jacksonville", "FL"),
    ("Kansas City", "MO"),
    ("Las Vegas", "NV"),
    ("Los Angeles", "CA"),
    ("Memphis", "TN"),
    ("Miami", "FL"),
    ("Minneapolis", "MN"),
    ("Nashville", "TN"),
    ("Newark", "NJ"),
    ("New York", "NY"),
    ("Oakland", "CA"),
    ("Phoenix", "AZ"),
    ("Portland", "OR"),
    ("Reno", "NV"),
    ("Salt Lake City", "UT"),
    ("Savannah", "GA"),
    ("Seattle", "WA"),
    ("St. Louis", "MO"),
    ("Tampa", "FL"),
]

HUBS = [
    ("Chicago", "IL"),
    ("Dallas", "TX"),
    ("Denver", "CO"),
    ("Memphis", "TN"),
    ("Newark", "NJ"),
    ("Phoenix", "AZ"),
    ("Salt Lake City", "UT"),
]


def dollars(value: float) -> float:
    return round(float(value), 2)


def generate_carriers() -> pd.DataFrame:
    carrier_names = [
        "NorthStar Freight",
        "BlueLine Logistics",
        "Summit Transport",
        "HarborLink Carriers",
        "Prairie Roadways",
        "MetroParcel Express",
        "IronRail Intermodal",
        "Canyon Trucking",
        "Evergreen Freight Co.",
        "Pioneer Drayage",
    ]

    rows = []
    for index, name in enumerate(carrier_names, start=1):
        on_time_rate = round(float(rng.uniform(0.82, 0.98)), 3)
        avg_transit_days = round(float(rng.uniform(1.2, 6.5)), 1)
        risk_score = round((1 - on_time_rate) * 70 + avg_transit_days * 3 + rng.uniform(0, 8), 1)
        rows.append(
            {
                "carrier_id": f"CAR-{index:03d}",
                "carrier_name": name,
                "carrier_type": CARRIER_TYPES[(index - 1) % len(CARRIER_TYPES)],
                "on_time_rate": on_time_rate,
                "avg_transit_days": avg_transit_days,
                "risk_score": min(risk_score, 100.0),
            }
        )

    return pd.DataFrame(rows)


def generate_customers() -> pd.DataFrame:
    prefixes = [
        "Acme",
        "Beacon",
        "Cobalt",
        "Evergreen",
        "Frontier",
        "Granite",
        "Horizon",
        "Keystone",
        "Liberty",
        "Meridian",
    ]
    suffixes = ["Supply", "Brands", "Distribution", "Works", "Systems", "Industries"]

    rows = []
    for index in range(1, N_CUSTOMERS + 1):
        rows.append(
            {
                "customer_id": f"CUS-{index:03d}",
                "customer_name": f"{random.choice(prefixes)} {random.choice(suffixes)} {index}",
                "customer_tier": random.choices(CUSTOMER_TIERS, weights=[0.12, 0.25, 0.28, 0.35])[0],
                "industry": random.choice(INDUSTRIES),
                "region": random.choice(REGIONS),
            }
        )

    return pd.DataFrame(rows)


def generate_routes() -> pd.DataFrame:
    rows = []
    used_lanes = set()

    while len(rows) < N_ROUTES:
        origin = random.choice(CITY_STATE_PAIRS)
        destination = random.choice(CITY_STATE_PAIRS)
        if origin == destination or (origin, destination) in used_lanes:
            continue

        used_lanes.add((origin, destination))
        route_number = len(rows) + 1
        distance = int(rng.integers(120, 2_800))
        lane_type = random.choice(LANE_TYPES)
        if distance > 1_000:
            lane_type = random.choice(["Long-haul", "Intermodal", "Cross-border"])
        delay_base = rng.uniform(0.05, 0.22) + (0.04 if distance > 1_200 else 0)

        rows.append(
            {
                "route_id": f"RTE-{route_number:03d}",
                "origin_city": origin[0],
                "origin_state": origin[1],
                "destination_city": destination[0],
                "destination_state": destination[1],
                "distance_miles": distance,
                "lane_type": lane_type,
                "historical_delay_rate": round(min(float(delay_base), 0.35), 3),
            }
        )

    return pd.DataFrame(rows)


def transit_days(distance_miles: int, carrier_avg_days: float, mode: str) -> int:
    mode_adjustment = {
        "Parcel": -1,
        "Truckload": 0,
        "Less-than-truckload": 1,
        "Rail": 2,
        "Intermodal": 2,
    }
    distance_days = max(1, int(np.ceil(distance_miles / 550)))
    estimate = round((distance_days + carrier_avg_days) / 2) + mode_adjustment.get(mode, 0)
    return max(1, int(estimate))


def generate_shipments(
    carriers: pd.DataFrame, customers: pd.DataFrame, routes: pd.DataFrame
) -> pd.DataFrame:
    carrier_lookup = carriers.set_index("carrier_id").to_dict("index")
    route_lookup = routes.set_index("route_id").to_dict("index")

    start_date = pd.Timestamp("2025-01-01")
    end_date = pd.Timestamp("2025-12-31")
    date_range_days = (end_date - start_date).days

    rows = []
    for index in range(1, N_SHIPMENTS + 1):
        shipment_id = f"SHP-{1000 + index}"
        customer_id = random.choice(customers["customer_id"].to_list())
        carrier_id = random.choice(carriers["carrier_id"].to_list())
        route_id = random.choice(routes["route_id"].to_list())
        route = route_lookup[route_id]
        carrier = carrier_lookup[carrier_id]
        mode = random.choices(SHIPMENT_MODES, weights=[0.42, 0.24, 0.16, 0.08, 0.10])[0]

        ship_date = start_date + pd.Timedelta(days=int(rng.integers(0, date_range_days)))
        planned_days = transit_days(route["distance_miles"], carrier["avg_transit_days"], mode)
        planned_delivery_date = ship_date + pd.Timedelta(days=planned_days)

        delay_probability = min(
            0.6,
            route["historical_delay_rate"] + (1 - carrier["on_time_rate"]) + rng.uniform(-0.03, 0.06),
        )
        is_delayed = bool(rng.random() < delay_probability)
        delay_days = int(rng.integers(1, 7)) if is_delayed else 0
        actual_delivery_date = planned_delivery_date + pd.Timedelta(days=delay_days)
        exception_probability = 0.08 + (0.24 if is_delayed else 0) + (0.08 if mode == "Intermodal" else 0)
        exception_flag = bool(rng.random() < exception_probability)

        rate_per_mile = {
            "Truckload": rng.uniform(2.0, 3.4),
            "Less-than-truckload": rng.uniform(1.3, 2.4),
            "Parcel": rng.uniform(0.9, 1.8),
            "Rail": rng.uniform(1.1, 2.0),
            "Intermodal": rng.uniform(1.4, 2.5),
        }[mode]
        weight_lbs = int(rng.integers(80, 44_000))
        freight_cost = dollars(route["distance_miles"] * rate_per_mile + weight_lbs * rng.uniform(0.015, 0.055))

        rows.append(
            {
                "shipment_id": shipment_id,
                "customer_id": customer_id,
                "carrier_id": carrier_id,
                "route_id": route_id,
                "ship_date": ship_date.date().isoformat(),
                "planned_delivery_date": planned_delivery_date.date().isoformat(),
                "actual_delivery_date": actual_delivery_date.date().isoformat(),
                "shipment_status": "DELIVERED_LATE" if is_delayed else "DELIVERED",
                "shipment_mode": mode,
                "weight_lbs": weight_lbs,
                "freight_cost": freight_cost,
                "is_delayed": is_delayed,
                "delay_days": delay_days,
                "exception_flag": exception_flag,
            }
        )

    return pd.DataFrame(rows)


def event_description(event_type: str) -> str:
    descriptions = {
        "CREATED": "Shipment tender created.",
        "PICKED_UP": "Freight picked up from origin facility.",
        "IN_TRANSIT": "Shipment is moving toward the next facility.",
        "ARRIVED_AT_HUB": "Shipment arrived at a carrier hub.",
        "OUT_FOR_DELIVERY": "Shipment departed final facility for delivery.",
        "DELIVERED": "Shipment delivered to consignee.",
        "DELAYED": "Shipment delayed against the planned schedule.",
        "CUSTOMS_HOLD": "Shipment held for customs or compliance review.",
    }
    return descriptions[event_type]


def build_event_sequence(is_delayed: bool, exception_flag: bool, event_count: int) -> list[str]:
    middle_events = ["IN_TRANSIT", "ARRIVED_AT_HUB"]
    if is_delayed:
        middle_events.append("DELAYED")
    if exception_flag and random.random() < 0.35:
        middle_events.append("CUSTOMS_HOLD")

    sequence = ["CREATED", "PICKED_UP"]
    if event_count == 3:
        return [*sequence, "DELIVERED"]

    while len(sequence) < event_count - 2:
        sequence.append(random.choice(middle_events))
    sequence.extend(["OUT_FOR_DELIVERY", "DELIVERED"])
    return sequence


def generate_shipment_events(shipments: pd.DataFrame, routes: pd.DataFrame) -> pd.DataFrame:
    route_lookup = routes.set_index("route_id").to_dict("index")
    rows = []
    event_number = 1

    for shipment in shipments.to_dict("records"):
        route = route_lookup[shipment["route_id"]]
        ship_start = pd.Timestamp(shipment["ship_date"])
        delivery_end = pd.Timestamp(shipment["actual_delivery_date"]) + pd.Timedelta(hours=18)
        event_count = int(rng.integers(3, 8))
        sequence = build_event_sequence(shipment["is_delayed"], shipment["exception_flag"], event_count)

        total_hours = max(1, int((delivery_end - ship_start).total_seconds() // 3600))
        offsets = sorted(rng.choice(np.arange(total_hours + 1), size=event_count, replace=False).tolist())

        for offset, event_type in zip(offsets, sequence):
            if event_type in {"CREATED", "PICKED_UP"}:
                city, state = route["origin_city"], route["origin_state"]
            elif event_type in {"OUT_FOR_DELIVERY", "DELIVERED"}:
                city, state = route["destination_city"], route["destination_state"]
            else:
                city, state = random.choice(HUBS)

            rows.append(
                {
                    "event_id": f"EVT-{event_number:06d}",
                    "shipment_id": shipment["shipment_id"],
                    "event_timestamp": (ship_start + pd.Timedelta(hours=int(offset))).isoformat(),
                    "event_type": event_type,
                    "event_city": city,
                    "event_state": state,
                    "event_description": event_description(event_type),
                }
            )
            event_number += 1

    return pd.DataFrame(rows)


def generate_exceptions(shipments: pd.DataFrame) -> pd.DataFrame:
    exception_types = [
        "Weather delay",
        "Carrier capacity constraint",
        "Customs hold",
        "Address issue",
        "Mechanical breakdown",
        "Missed appointment",
    ]
    actions = {
        "Weather delay": "Monitor weather window and notify customer of revised ETA.",
        "Carrier capacity constraint": "Escalate to carrier manager and evaluate backup carrier.",
        "Customs hold": "Request missing documents and validate customs broker handoff.",
        "Address issue": "Confirm delivery address with customer operations contact.",
        "Mechanical breakdown": "Ask carrier for recovery truck assignment and updated ETA.",
        "Missed appointment": "Reschedule dock appointment and update delivery plan.",
    }

    rows = []
    exception_shipments = shipments[shipments["exception_flag"]].reset_index(drop=True)
    for index, shipment in exception_shipments.iterrows():
        exception_type = random.choice(exception_types)
        ship_date = pd.Timestamp(shipment["ship_date"])
        actual_delivery = pd.Timestamp(shipment["actual_delivery_date"])
        hours_available = max(1, int((actual_delivery - ship_date).total_seconds() // 3600))
        detected_at = ship_date + pd.Timedelta(hours=int(rng.integers(1, hours_available + 1)))

        rows.append(
            {
                "exception_id": f"EXC-{index + 1:05d}",
                "shipment_id": shipment["shipment_id"],
                "exception_type": exception_type,
                "severity": random.choices(["Low", "Medium", "High", "Critical"], weights=[0.20, 0.46, 0.27, 0.07])[0],
                "detected_at": detected_at.isoformat(),
                "resolution_status": random.choices(
                    ["Resolved", "Monitoring", "Escalated"], weights=[0.62, 0.25, 0.13]
                )[0],
                "recommended_action": actions[exception_type],
            }
        )

    return pd.DataFrame(rows)


def write_csv(name: str, dataframe: pd.DataFrame) -> None:
    dataframe.to_csv(OUTPUT_DIR / name, index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    carriers = generate_carriers()
    customers = generate_customers()
    routes = generate_routes()
    shipments = generate_shipments(carriers, customers, routes)
    shipment_events = generate_shipment_events(shipments, routes)
    exceptions = generate_exceptions(shipments)

    datasets = {
        "carriers.csv": carriers,
        "customers.csv": customers,
        "routes.csv": routes,
        "shipments.csv": shipments,
        "shipment_events.csv": shipment_events,
        "exceptions.csv": exceptions,
    }

    for filename, dataframe in datasets.items():
        write_csv(filename, dataframe)

    print("Synthetic logistics data generated:")
    for filename, dataframe in datasets.items():
        print(f"- {filename}: {len(dataframe):,} rows")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
