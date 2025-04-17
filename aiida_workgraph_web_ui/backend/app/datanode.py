from typing import List, Dict, Any, Union
from fastapi import APIRouter, HTTPException, Query
from aiida import orm
import json

router = APIRouter()


@router.get("/api/datanode-data")
async def read_datanode_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(15, gt=0, le=500),
    sortField: str = Query("pk", pattern="^(pk|ctime|node_type|label|description)$"),
    sortOrder: str = Query("desc", pattern="^(asc|desc)$"),
    filterModel: str | None = Query(None),  # <-- NEW
) -> Dict[str, Any]:
    """
    Return a page slice, total row count, **plus server‑side filtering**.
    """
    from aiida.orm import QueryBuilder, Data
    from aiida_workgraph_web_ui.backend.app.utils import time_ago

    qb = QueryBuilder()
    filters = {}

    # ------------ translate DataGrid's filter model ------------ #
    if filterModel:
        try:
            fm = json.loads(filterModel)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid filterModel JSON"
            ) from exc

        for item in fm.get("items", []):
            field = item.get("field")
            value = item.get("value")
            operator = item.get("operator", "contains")

            if not value:
                continue

            # map DataGrid fields to AiiDA columns
            field_map = {
                "pk": "id",
                "ctime": "ctime",
                "node_type": "node_type",
                "label": "label",
                "description": "description",
            }
            if field not in field_map:
                continue  # silently ignore unknown fields

            col = field_map[field]

            if col == "id":  # numeric pk
                try:
                    filters[col] = int(value)
                except ValueError:
                    continue
            else:  # string columns
                if operator in ("contains", "equals", "is"):
                    filters[col] = {"like": f"%{value}%"}
                # add more operator translations here as needed
        # ---------- quick‑filter values (NEW) -------------------
        qf_values = fm.get("quickFilterValues", [])
        if qf_values:
            # each value must match at least one column
            or_blocks_per_value = []
            for value in qf_values:
                like = {"like": f"%{value}%"}
                or_block = {
                    "or": [
                        {"id": int(value)} if value.isdigit() else {},
                        {"node_type": like},
                        {"label": like},
                        {"description": like},
                    ]
                }
                or_blocks_per_value.append(or_block)

            # combine with existing filters using AND
            if filters:
                filters = {"and": [filters, *or_blocks_per_value]}
            else:
                filters = {"and": or_blocks_per_value}

    # ------------------ base query ------------------ #
    qb.append(
        Data,
        filters=filters,
        project=["id", "uuid", "ctime", "node_type", "label", "description"],
        tag="d",
    )

    # -------------- server‑side order / paging -------------- #
    col_map = {
        "pk": "id",
        "ctime": "ctime",
        "node_type": "node_type",
        "label": "label",
        "description": "description",
    }
    qb.order_by({"d": {col_map[sortField]: sortOrder}})
    total_rows = qb.count()
    qb.offset(skip).limit(limit)

    page = [
        {
            "pk": pk,
            "uuid": uuid,
            "ctime": time_ago(ctime),
            "node_type": node_type,
            "label": label,
            "description": description,
        }
        for pk, uuid, ctime, node_type, label, description in qb.all()
    ]
    return {"total": total_rows, "data": page}


@router.get("/api/datanode/{id}")
async def read_data_node_item(id: int) -> Dict[str, Any]:

    try:
        node = orm.load_node(id)
        content = node.backend_entity.attributes
        content["node_type"] = node.node_type
        return content
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Data node {id} not found")


# Route for deleting a datanode item
@router.delete("/api/datanode/delete/{id}")
async def delete_data_node(
    id: int,
    dry_run: bool = False,
) -> Dict[str, Union[bool, str, List[int]]]:
    from aiida.tools import delete_nodes

    try:
        # Perform the delete action here
        deleted_nodes, was_deleted = delete_nodes([id], dry_run=dry_run)
        if was_deleted:
            return {
                "deleted": True,
                "message": f"Deleted data node {id}",
                "deleted_nodes": list(deleted_nodes),
            }
        else:
            message = f"Did not delete data node {id}"
            if dry_run:
                message += " [dry-run]"
            return {
                "deleted": False,
                "message": message,
                "deleted_nodes": list(deleted_nodes),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
