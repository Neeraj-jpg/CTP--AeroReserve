"""Fictional AeroSky sample network and repeatable daily timetable.

The schedule is deliberately labelled fictional. The app does not call a live
airline, airport or fare API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aerobooking.models import Airport, Flight

AIRLINE_NAME = "AeroSky (sample airline)"
INDIA_TZ = ZoneInfo("Asia/Kolkata")
MIN_DATE_RANGE_DAYS = 180


def india_today() -> date:
    """Current calendar date at the schedule's Indian Standard Time location."""
    return datetime.now(INDIA_TZ).date()


AIRPORTS: tuple[Airport, ...] = (
    Airport("VGA", "Vijayawada", "Vijayawada International Airport"),
    Airport("HYD", "Hyderabad", "Rajiv Gandhi International Airport"),
    Airport("BLR", "Bengaluru", "Kempegowda International Airport"),
    Airport("BOM", "Mumbai", "Chhatrapati Shivaji Maharaj International Airport"),
    Airport("DEL", "New Delhi", "Indira Gandhi International Airport"),
    Airport("MAA", "Chennai", "Chennai International Airport"),
    Airport("GOI", "Goa", "Manohar International Airport"),
)
AIRPORT_BY_CODE = {airport.code: airport for airport in AIRPORTS}


@dataclass(frozen=True, slots=True)
class FlightTemplate:
    number: str
    origin: str
    destination: str
    departure: str
    arrival: str
    distance_km: float
    aircraft: str = "A320"


# All times are local Indian Standard Time. A few evening flights are provided
# so reverse journeys and later same-day connections can be demonstrated.
FLIGHT_TEMPLATES: tuple[FlightTemplate, ...] = (
    FlightTemplate("AS101", "VGA", "HYD", "06:00", "07:15", 270),
    FlightTemplate("AS205", "HYD", "DEL", "08:30", "10:55", 1250),
    FlightTemplate("AS206", "HYD", "BLR", "08:45", "10:00", 500),
    FlightTemplate("AS301", "VGA", "BLR", "09:15", "10:45", 820),
    FlightTemplate("AS306", "BLR", "DEL", "11:30", "14:00", 1740),
    FlightTemplate("AS110", "VGA", "DEL", "06:40", "09:15", 1370),
    FlightTemplate("AS120", "VGA", "BOM", "12:00", "14:10", 850),
    FlightTemplate("AS403", "BOM", "DEL", "15:00", "17:10", 1150),
    FlightTemplate("AS401", "BLR", "BOM", "11:15", "13:05", 840),
    FlightTemplate("AS411", "BOM", "HYD", "16:00", "17:30", 620),
    FlightTemplate("AS501", "DEL", "MAA", "15:00", "18:00", 1760),
    FlightTemplate("AS502", "MAA", "BLR", "19:00", "20:05", 290),
    FlightTemplate("AS601", "HYD", "MAA", "12:30", "14:20", 625),
    FlightTemplate("AS602", "BOM", "MAA", "15:00", "17:30", 1030),
    FlightTemplate("AS102", "HYD", "VGA", "18:00", "19:15", 270),
    FlightTemplate("AS207", "DEL", "HYD", "17:30", "19:55", 1250),
    FlightTemplate("AS307", "DEL", "BLR", "15:00", "17:30", 1740),
    FlightTemplate("AS302", "BLR", "VGA", "18:30", "20:00", 820),
    FlightTemplate("AS111", "DEL", "VGA", "19:00", "21:35", 1370),
    FlightTemplate("AS121", "BOM", "VGA", "16:00", "18:10", 850),
    FlightTemplate("AS404", "DEL", "BOM", "18:00", "20:10", 1150),
    FlightTemplate("AS402", "BOM", "BLR", "18:00", "19:50", 840),
    FlightTemplate("AS412", "HYD", "BOM", "19:00", "20:30", 620),
    FlightTemplate("AS701", "BLR", "GOI", "15:00", "16:10", 485),
    FlightTemplate("AS702", "GOI", "BOM", "17:00", "18:20", 430),
    FlightTemplate("AS703", "BOM", "GOI", "10:00", "11:20", 430),
    FlightTemplate("AS704", "GOI", "BLR", "13:00", "14:10", 485),
)


def flights_for_date(travel_date: date) -> tuple[Flight, ...]:
    """Materialise a dated set of sample flight instances for one calendar day."""
    result: list[Flight] = []
    for template in FLIGHT_TEMPLATES:
        depart_h, depart_m = map(int, template.departure.split(":"))
        arrive_h, arrive_m = map(int, template.arrival.split(":"))
        departure = datetime.combine(travel_date, time(depart_h, depart_m))
        arrival = datetime.combine(travel_date, time(arrive_h, arrive_m))
        if arrival <= departure:
            arrival += timedelta(days=1)
        result.append(
            Flight(
                flight_id=f"{template.number}-{travel_date.isoformat()}",
                flight_number=template.number,
                airline=AIRLINE_NAME,
                travel_date=travel_date,
                origin=AIRPORT_BY_CODE[template.origin],
                destination=AIRPORT_BY_CODE[template.destination],
                departure_at=departure,
                arrival_at=arrival,
                distance_km=template.distance_km,
                aircraft=template.aircraft,
            )
        )
    return tuple(sorted(result, key=lambda flight: (flight.departure_at, flight.flight_number)))


def airport(code: str) -> Airport:
    try:
        return AIRPORT_BY_CODE[code.upper()]
    except KeyError as exc:
        raise ValueError(f"unknown airport code: {code}") from exc
