import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _col_row(ref: str) -> tuple[int, int]:
    col = ""
    row = ""
    for char in ref:
        if char.isalpha():
            col += char
        else:
            row += char
    number = 0
    for char in col:
        number = number * 26 + (ord(char.upper()) - 64)
    return number, int(row)


def _excel_date(value: str) -> str:
    return (datetime(1899, 12, 30) + timedelta(days=float(value))).date().isoformat()


def load_workbook(path: Path) -> dict[str, list[dict[int, str]]]:
    with zipfile.ZipFile(path) as workbook:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append("".join(node.text or "" for node in item.iter(f"{MAIN}t")))
        book = ET.fromstring(workbook.read("xl/workbook.xml"))
        rels = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheets: dict[str, list[dict[int, str]]] = {}
        for sheet in book.findall("m:sheets/m:sheet", NS):
            name = sheet.attrib["name"]
            target = targets[sheet.attrib[f"{REL}id"]]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            root = ET.fromstring(workbook.read(target))
            rows: dict[int, dict[int, str]] = {}
            for cell in root.iter(f"{MAIN}c"):
                ref = cell.attrib.get("r")
                if not ref:
                    continue
                col, row_number = _col_row(ref)
                kind = cell.attrib.get("t")
                value_node = cell.find(f"{MAIN}v")
                if kind == "s" and value_node is not None and value_node.text:
                    value = shared[int(value_node.text)]
                elif value_node is not None and value_node.text is not None:
                    value = value_node.text
                else:
                    value = ""
                rows.setdefault(row_number, {})[col] = value
            ordered = [rows[index] for index in range(1, (max(rows) if rows else 0) + 1)]
            sheets[name] = ordered
        return sheets


def read_source(path: Path) -> dict:
    sheets = load_workbook(path)
    agents = []
    for row in sheets["Agent Master"][1:]:
        if not row.get(1):
            continue
        agents.append(
            {
                "agent_id": row[1],
                "agent_name": row[2],
                "team": row[3],
                "team_lead": row[4],
                "default_shift": row[5],
                "employment_status": row[6],
                "productive_hours": float(row[7]),
            }
        )
    agent_shift = {agent["agent_id"]: agent["default_shift"] for agent in agents}
    roster = []
    for row in sheets["Monthly Roster"][1:]:
        if not row.get(1):
            continue
        agent_id = row[2]
        status = row.get(7, "")
        shift = row.get(6) or agent_shift.get(agent_id, "")
        roster.append(
            {
                "roster_date": _excel_date(row[1]),
                "agent_id": agent_id,
                "shift": shift,
                "attendance_status": status,
            }
        )
    forecast = []
    for row in sheets["Forecast Capacity"][1:]:
        if not row.get(1):
            continue
        forecast.append(
            {
                "roster_date": _excel_date(row[1]),
                "forecast_volume": int(float(row[2])),
                "aht_seconds": int(float(row[3])),
                "shrinkage": str(row[4]),
                "occupancy": str(row[5]),
                "required_agents": str(row[6]),
            }
        )
    return {"agents": agents, "roster": roster, "forecast": forecast}
