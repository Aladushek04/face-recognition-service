"""Shared country allow-list helpers for StashDB import and cleanup scripts."""

from __future__ import annotations

import re
import unicodedata


COUNTRY_REGION_FILTERS = {
    "preferred-map": "green countries from the user map",
    "americas-europe-russia": "North America, South America, Europe, and Russia",
}

NORTH_AMERICA_COUNTRIES = {
    "antigua and barbuda",
    "bahamas",
    "barbados",
    "belize",
    "canada",
    "costa rica",
    "cuba",
    "dominica",
    "dominican republic",
    "el salvador",
    "grenada",
    "guatemala",
    "haiti",
    "honduras",
    "jamaica",
    "mexico",
    "nicaragua",
    "panama",
    "saint kitts and nevis",
    "saint lucia",
    "saint vincent and the grenadines",
    "trinidad and tobago",
    "united states",
    "united states of america",
    "usa",
    "us",
}
SOUTH_AMERICA_COUNTRIES = {
    "argentina",
    "bolivia",
    "brazil",
    "chile",
    "colombia",
    "ecuador",
    "guyana",
    "paraguay",
    "peru",
    "suriname",
    "uruguay",
    "venezuela",
}
EUROPE_COUNTRIES = {
    "albania",
    "andorra",
    "austria",
    "belarus",
    "belgium",
    "bosnia and herzegovina",
    "bulgaria",
    "croatia",
    "czech republic",
    "czechia",
    "denmark",
    "estonia",
    "finland",
    "france",
    "germany",
    "greece",
    "hungary",
    "iceland",
    "ireland",
    "italy",
    "kosovo",
    "latvia",
    "liechtenstein",
    "lithuania",
    "luxembourg",
    "malta",
    "moldova",
    "monaco",
    "montenegro",
    "netherlands",
    "north macedonia",
    "norway",
    "poland",
    "portugal",
    "romania",
    "russia",
    "russian federation",
    "san marino",
    "serbia",
    "slovakia",
    "slovenia",
    "spain",
    "sweden",
    "switzerland",
    "ukraine",
    "united kingdom",
    "uk",
    "great britain",
    "england",
    "scotland",
    "wales",
    "northern ireland",
    "vatican city",
}
PREFERRED_EXTRA_COUNTRIES = {
    "australia",
    "cook islands",
    "cyprus",
    "fiji",
    "kazakhstan",
    "new zealand",
    "papua new guinea",
    "samoa",
    "saudi arabia",
    "tonga",
    "turkey",
}
COUNTRY_REGION_COUNTRIES = {
    "americas-europe-russia": NORTH_AMERICA_COUNTRIES | SOUTH_AMERICA_COUNTRIES | EUROPE_COUNTRIES,
    "preferred-map": (
        NORTH_AMERICA_COUNTRIES
        | SOUTH_AMERICA_COUNTRIES
        | EUROPE_COUNTRIES
        | PREFERRED_EXTRA_COUNTRIES
    ),
}
COUNTRY_ALIASES = {
    "ad": "andorra",
    "ag": "antigua and barbuda",
    "al": "albania",
    "america": "united states",
    "am": "armenia",
    "ar": "argentina",
    "at": "austria",
    "au": "australia",
    "az": "azerbaijan",
    "ba": "bosnia and herzegovina",
    "bb": "barbados",
    "be": "belgium",
    "bg": "bulgaria",
    "bo": "bolivia",
    "br": "brazil",
    "brasil": "brazil",
    "bs": "bahamas",
    "by": "belarus",
    "bz": "belize",
    "ca": "canada",
    "ch": "switzerland",
    "cl": "chile",
    "co": "colombia",
    "cr": "costa rica",
    "cu": "cuba",
    "cy": "cyprus",
    "cz": "czechia",
    "czech republic": "czechia",
    "de": "germany",
    "deutschland": "germany",
    "dk": "denmark",
    "dm": "dominica",
    "do": "dominican republic",
    "ec": "ecuador",
    "ee": "estonia",
    "england": "united kingdom",
    "es": "spain",
    "fi": "finland",
    "fj": "fiji",
    "fr": "france",
    "gb": "united kingdom",
    "gd": "grenada",
    "ge": "georgia",
    "great britain": "united kingdom",
    "gr": "greece",
    "gt": "guatemala",
    "gy": "guyana",
    "hn": "honduras",
    "holland": "netherlands",
    "hr": "croatia",
    "ht": "haiti",
    "hu": "hungary",
    "ie": "ireland",
    "is": "iceland",
    "it": "italy",
    "jm": "jamaica",
    "kn": "saint kitts and nevis",
    "kz": "kazakhstan",
    "lc": "saint lucia",
    "li": "liechtenstein",
    "lt": "lithuania",
    "lu": "luxembourg",
    "lv": "latvia",
    "mc": "monaco",
    "md": "moldova",
    "me": "montenegro",
    "mk": "north macedonia",
    "mt": "malta",
    "mx": "mexico",
    "ni": "nicaragua",
    "nl": "netherlands",
    "no": "norway",
    "northern ireland": "united kingdom",
    "nz": "new zealand",
    "pa": "panama",
    "pe": "peru",
    "pg": "papua new guinea",
    "pl": "poland",
    "pt": "portugal",
    "py": "paraguay",
    "republic of moldova": "moldova",
    "ro": "romania",
    "rs": "serbia",
    "ru": "russia",
    "russian federation": "russia",
    "sa": "saudi arabia",
    "saudi": "saudi arabia",
    "saudi arabian": "saudi arabia",
    "scotland": "united kingdom",
    "se": "sweden",
    "si": "slovenia",
    "sk": "slovakia",
    "sr": "suriname",
    "sv": "el salvador",
    "the netherlands": "netherlands",
    "tr": "turkey",
    "tt": "trinidad and tobago",
    "tuerkiye": "turkey",
    "turkiye": "turkey",
    "ua": "ukraine",
    "uk": "united kingdom",
    "u k": "united kingdom",
    "united states of america": "united states",
    "us": "united states",
    "u s": "united states",
    "usa": "united states",
    "u s a": "united states",
    "uy": "uruguay",
    "va": "vatican city",
    "vc": "saint vincent and the grenadines",
    "ve": "venezuela",
    "wales": "united kingdom",
    "xk": "kosovo",
}


def normalize_country(value: str | None) -> str | None:
    """Normalize country text for stable allow/block-list matching."""
    if not value:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("&", " and ").replace("_", " ").replace("-", " ")
    normalized = re.sub(r"[^a-zA-Z ]+", " ", normalized).lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return None
    return COUNTRY_ALIASES.get(normalized, normalized)


def parse_country_list(value: str | None) -> set[str]:
    countries: set[str] = set()
    for item in (value or "").split(","):
        country = normalize_country(item)
        if country:
            countries.add(country)
    return countries


def allowed_countries_for_region(region: str | None) -> set[str]:
    if not region:
        return set()
    return {
        normalized
        for country in COUNTRY_REGION_COUNTRIES[region]
        if (normalized := normalize_country(country))
    }
