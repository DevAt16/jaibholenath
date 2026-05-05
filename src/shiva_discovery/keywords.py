from __future__ import annotations


PHASE1_KEYWORDS: tuple[str, ...] = (
    "Shiva temple",
    "Shiv Mandir",
    "Mahadev temple",
    "Mahadev Mandir",
    "Shankar Mandir",
    "Someshwar temple",
    "Vishwanath temple",
    "Lingeshwar temple",
    "Rudreshwar temple",
)

HIGH_CONFIDENCE_TERMS: tuple[str, ...] = (
    "shiva",
    "shiv",
    "mahadev",
    "mahadeva",
    "mahakal",
    "mahakaleshwar",
    "vishwanath",
    "somnath",
    "kedarnath",
    "omkareshwar",
    "trimbakeshwar",
    "bhimashankar",
    "rameshwaram",
    "nageshwar",
    "mallikarjuna",
    "lingeshwar",
    "linga",
    "lingam",
)

MEDIUM_CONFIDENCE_TERMS: tuple[str, ...] = (
    "shankar",
    "shankara",
    "ishwar",
    "eshwar",
    "nath",
    "rudra",
    "rudreshwar",
    "someshwar",
    "bholenath",
)

DEFAULT_TASK_LOCATION_TYPES: tuple[str, ...] = (
    "district",
    "town",
    "urban_local_body",
)

OPTIONAL_CITY_TASK_TYPES: tuple[str, ...] = ("city",)
OPTIONAL_VILLAGE_TASK_TYPES: tuple[str, ...] = ("village",)

SEARCH_PRIORITY_BY_TYPE: dict[str, int] = {
    "state": 10,
    "district": 20,
    "sub_district": 30,
    "city": 40,
    "town": 45,
    "urban_local_body": 50,
    "village": 90,
}
