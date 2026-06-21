import os
import sys
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = os.environ.get(
    "ENDPOINT",
    "https://wabi-west-europe-d-primary-api.analysis.windows.net/public/reports/querydata",
)
EMBED_KEY = os.environ["EMBED_KEY"]
DATASET_ID = os.environ["DATASET_ID"]
REPORT_ID = os.environ["REPORT_ID"]
VISUAL_ID = os.environ["VISUAL_ID"]
MODEL_ID = int(os.environ["MODEL_ID"])
HA_WEBHOOK_URL = os.environ["HA_WEBHOOK_URL"]

HEADERS = {
    "Content-Type": "application/json",
    "X-PowerBI-ResourceKey": EMBED_KEY,
}


def _col(source, prop):
    return {"Column": {"Expression": {"SourceRef": {"Source": source}}, "Property": prop}}


def _in(col, value):
    return {"Condition": {"In": {"Expressions": [col], "Values": [[{"Literal": {"Value": value}}]]}}}


def _not_contains(col, value):
    return {"Not": {"Expression": {"Contains": {"Left": col, "Right": {"Literal": {"Value": value}}}}}}


def _build_query(address: str, where_extras: list, from_extras: list = None) -> dict:
    from_tables = [
        {"Name": "s", "Entity": "ScheduleDates", "Type": 0},
        {"Name": "w", "Entity": "WasteObject", "Type": 0},
        {"Name": "t", "Entity": "Teritorijos konteinerių tvarkaraščiams", "Type": 0},
    ]
    if from_extras:
        from_tables += from_extras

    where = [
        _in(_col("w", "Adresas"), f"'{address}'"),
        *where_extras,
        _in(_col("s", "Future"), "'true'"),
        _in(_col("t", "Rodomas tvarkaraštis"), "'1'"),
        _in(_col("s", "OverNextRun"), "true"),
        {"Condition": {"Not": {"Expression": {"Comparison": {
            "ComparisonKind": 0,
            "Left": _col("w", "Inventorinis nr."),
            "Right": {"Literal": {"Value": "null"}},
        }}}}},
        {"Condition": {"And": {
            "Left": _not_contains(_col("w", "Inventorinis nr."), "'siuks'"),
            "Right": _not_contains(_col("w", "Inventorinis nr."), "'šiuk'"),
        }}},
    ]

    return {
        "version": "1.0.0",
        "queries": [{
            "Query": {
                "Commands": [{
                    "SemanticQueryDataShapeCommand": {
                        "Query": {
                            "Version": 2,
                            "From": from_tables,
                            "Select": [{
                                "Measure": {
                                    "Expression": {"SourceRef": {"Source": "s"}},
                                    "Property": "Datos",
                                },
                                "Name": "ScheduleDates.Datos",
                            }],
                            "Where": where,
                        },
                        "Binding": {
                            "Primary": {"Groupings": [{"Projections": [0]}]},
                            "DataReduction": {"DataVolume": 3, "Primary": {"Top": {}}},
                            "Version": 1,
                        },
                        "ExecutionMetricsKind": 1,
                    }
                }]
            },
            "QueryId": "",
            "ApplicationContext": {
                "DatasetId": DATASET_ID,
                "Sources": [{"ReportId": REPORT_ID, "VisualId": VISUAL_ID}],
            },
        }],
        "cancelQueries": [],
        "modelId": MODEL_ID,
    }


def build_plastic_query(address: str, district: str) -> dict:
    return _build_query(
        address,
        where_extras=[_in(_col("a", "District"), f"'{district}'")],
        from_extras=[{"Name": "a", "Entity": "AllAddresses", "Type": 0}],
    )


def build_glass_query(address: str, inventory_nr: str) -> dict:
    return _build_query(
        address,
        where_extras=[_in(_col("w", "Inventorinis nr."), f"'{inventory_nr}'")],
    )


def _extract_dates(resp) -> list:
    resp.raise_for_status()
    raw = (
        resp.json()["results"][0]["result"]["data"]
        ["dsr"]["DS"][0]["PH"][0]["DM0"][0]["M0"]
    )
    return [d.strip() for d in raw.split(",")]


def get_plastic_schedule(address: str, district: str) -> list:
    resp = requests.post(
        ENDPOINT,
        headers=HEADERS,
        json=build_plastic_query(address, district),
        params={"synchronous": "true"},
    )
    return _extract_dates(resp)


def get_glass_schedule(address: str, inventory_nr: str) -> list:
    resp = requests.post(
        ENDPOINT,
        headers=HEADERS,
        json=build_glass_query(address, inventory_nr),
        params={"synchronous": "true"},
    )
    return _extract_dates(resp)


def send_to_ha(plastic_dates: list, glass_dates: list) -> None:
    text = "\n".join([
        f"Plastic: {', '.join(plastic_dates[:2])}",
        f"Glass: {', '.join(glass_dates[:2])}",
    ])
    payload = {"text": text}
    resp = requests.post(HA_WEBHOOK_URL, json=payload, verify=False, timeout=10)
    resp.raise_for_status()
    print(f"Sent to HA webhook: {payload}")


def main():
    address = os.environ["ADDRESS"]
    district = os.environ["DISTRICT"]
    glass_inventory_nr = os.environ["GLASS_INVENTORY_NR"]

    print(f"Address: {address}, {district}\n")

    plastic_dates = get_plastic_schedule(address, district)
    print(f"Plastic upcoming pickup dates ({len(plastic_dates)}):")
    for d in plastic_dates:
        print(f"  {d}")

    print()

    glass_dates = get_glass_schedule(address, glass_inventory_nr)
    print(f"Glass upcoming pickup dates ({len(glass_dates)}):")
    for d in glass_dates:
        print(f"  {d}")

    print()
    send_to_ha(plastic_dates, glass_dates)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        requests.post(HA_WEBHOOK_URL, json={"text": "Failed to query data"}, verify=False, timeout=10)
