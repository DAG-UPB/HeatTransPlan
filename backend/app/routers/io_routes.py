"""
I/O router — import/export JSON state and CSV.

Stateless, like the analysis endpoints: each call gets the project (or the
file) in the request and answers with the result. Nothing is kept on the
server.
"""

from typing import Any, Dict, Literal

from fastapi import APIRouter, Body, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from io import BytesIO
from datetime import datetime
import json

from app.models.project import ProjectState
from app.services.project_csv import (
    ProjectTooLarge, distance_csv, is_project_csv, project_csv, read_project_csv,
)

router = APIRouter()

# The handlers that parse or build a file are plain `def`: FastAPI runs them
# in its thread pool, so a large project does not hold up every other request
# the way `async def` would. They read the upload with file.file.read(), the
# blocking form, for the same reason.


# ---- JSON Import/Export ----

@router.post("/import-json")
def import_json(file: UploadFile = File(...)):
    """
    Read a project file (same format as save_app_state()) and return it as a
    checked project state. Nothing is kept.
    """
    try:
        content = file.file.read()
        data = json.loads(content.decode("utf-8"))
        return {"state": ProjectState(**data)}
    except Exception as e:
        raise HTTPException(400, f"Failed to import JSON: {e}")


@router.post("/import-json-body")
async def import_json_body(state: ProjectState):
    """Check a project state sent as the JSON body and return it. Nothing is
    kept."""
    return {"state": state}


@router.post("/export-json")
def export_json(project: ProjectState):
    """The project sent, as a JSON download."""
    data = project.model_dump()
    content = json.dumps(data, indent=2).encode("utf-8")
    buf = BytesIO(content)
    filename = f"heattransplan_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- CSV Export ----

def _csv_download(text: str, stem: str) -> StreamingResponse:
    filename = f"{stem}_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return StreamingResponse(
        BytesIO(text.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export-csv")
def export_csv(project: Dict[str, Any] = Body(...)):
    """The streams of the project sent, as CSV: one row per stream, semicolon
    separated (app/services/project_csv.py). The page's Export CSV, its
    export_csv command and the MCP tool all get this one format, and
    /import-csv reads it back. The project is taken as the page holds it."""
    try:
        return _csv_download(project_csv(project), "heattransplan_export")
    except ProjectTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc


@router.post("/export-distances")
def export_distances(project: Dict[str, Any] = Body(...),
                     metric: Literal["manhattan", "euclidean"] = "manhattan"):
    """Distances between the subprocesses of the project sent, in meters, as
    a CSV matrix: along north-south plus east-west (manhattan) or straight
    (euclidean)."""
    try:
        return _csv_download(distance_csv(project, metric), f"heattransplan_distances_{metric}")
    except ProjectTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc


# ---- CSV Import ----

@router.post("/import-csv")
def import_csv(file: UploadFile = File(...)):
    """Read process data from CSV and return the processes; the caller puts
    them into its project. Nothing is kept. Reads this app's own export
    (/export-csv: then also the process groups, their names and positions)
    and the older column format (name, next, conntemp, connm, conncp,
    stream_no, mdot, temp_in, temp_out, cp)."""
    try:
        import pandas as pd
        import io as _io

        content = file.file.read()
        text = content.decode("utf-8-sig")
        if is_project_csv(text):
            # This app's own export: processes, their groups and positions.
            out = read_project_csv(text)
            return {"imported_processes": len(out["processes"]), **out}
        # The older column format (name, next, conntemp, ...).
        df = pd.read_csv(_io.StringIO(text))

        required = {"name", "next", "conntemp", "connm", "conncp", "stream_no", "mdot", "temp_in", "temp_out", "cp"}
        if not required.issubset(df.columns):
            raise HTTPException(400, f"CSV missing required columns. Need: {required}")

        from app.models.process import ProcessNode
        from app.models.stream import StreamModel

        proc_lookup = {}
        procs = []
        for _, row in df.iterrows():
            key = (row["name"], row["next"], row["conntemp"], row.get("product_tout", ""), row["connm"], row["conncp"])
            if key not in proc_lookup:
                p = ProcessNode(
                    name=str(row.get("name", "")),
                    level=1,
                    next=str(row.get("next", "")),
                    conntemp=str(row.get("conntemp", "")),
                    product_tout=str(row.get("product_tout", "")),
                    connm=str(row.get("connm", "")),
                    conncp=str(row.get("conncp", "")),
                )
                procs.append(p)
                proc_lookup[key] = p
            stream_no = row.get("stream_no")
            if pd.notna(stream_no):
                proc_lookup[key].streams.append(StreamModel(
                    mdot=str(row.get("mdot", "")),
                    temp_in=str(row.get("temp_in", "")),
                    temp_out=str(row.get("temp_out", "")),
                    cp=str(row.get("cp", "")),
                ))

        return {"imported_processes": len(procs),
                "processes": [p.model_dump() for p in procs]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"CSV import failed: {e}")
