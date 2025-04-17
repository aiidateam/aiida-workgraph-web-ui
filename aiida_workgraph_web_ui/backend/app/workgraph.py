from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query, Body
from aiida import orm
from typing import List, Dict, Union, Optional
from aiida_workgraph.utils import get_parent_workgraphs
from aiida.orm.utils.serialize import deserialize_unsafe
import traceback

router = APIRouter()


@router.get("/api/workgraph-data")
async def read_workgraph_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(15, gt=0, le=500),
    sortField: str = Query(
        "pk", pattern="^(pk|ctime|process_label|state|label|description)$"
    ),
    sortOrder: str = Query("desc", pattern="^(asc|desc)$"),
    filterModel: Optional[str] = Query(None),
):
    """
    Identical contract to /api/datanode-data
    """
    from aiida.orm import QueryBuilder
    from aiida_workgraph.orm.workgraph import WorkGraphNode
    from aiida_workgraph_web_ui.backend.app.utils import (
        time_ago,
        translate_datagrid_filter_json,
    )

    qb = QueryBuilder()
    filters = {}

    # ——— translate the DataGrid filter model (same helper you used for DataNode) ———
    if filterModel:
        filters = translate_datagrid_filter_json(filterModel)  # factor out for reuse

    qb.append(
        WorkGraphNode,  # ⚡ adjust to your node type
        filters=filters,
        project=[
            "id",
            "uuid",
            "ctime",
            "attributes.process_label",
            "attributes.process_state",
            "attributes.process_status",
            "attributes.exit_status",
            "attributes.exit_message",
            "label",
            "description",
        ],
        tag="data",
    )

    col_map = {
        "pk": "id",
        "ctime": "ctime",
        "process_label": "attributes.process_label",
        "state": "attributes.process_state",
        "status": "attributes.process_status",
        "exit_status": "attributes.exit_status",
        "exit_message": "attributes.exit_message",
        "label": "label",
        "description": "description",
    }
    qb.order_by({"data": {col_map[sortField]: sortOrder}})

    total_rows = qb.count()
    qb.offset(skip).limit(limit)

    page = [
        {
            "pk": pk,
            "uuid": uuid,
            "ctime": time_ago(ctime),
            "process_label": plabel,
            "state": state.title(),
            "status": status,
            "exit_status": exit_status,
            "exit_message": exit_message,
            "label": label,
            "description": description,
        }
        for pk, uuid, ctime, plabel, state, status, exit_status, exit_message, label, description in qb.all()
    ]
    return {"total": total_rows, "data": page}


# ——— PUT /api/workgraph/{id} to update label/description ———
@router.put("/api/workgraph-data/{id}")
async def update_workgraph_node(
    id: int,
    payload: Dict[str, str] = Body(
        ..., examples={"label": "new-label", "description": "some text"}
    ),
):
    try:
        node = orm.load_node(id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"WorkGraph {id} not found")

    allowed = {"label", "description"}
    changed = False
    for key, value in payload.items():
        if key not in allowed:
            continue
        setattr(node, key, value)
        changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    return {"updated": True, "pk": id, **{k: getattr(node, k) for k in allowed}}


@router.get("/api/task/{id}/{path:path}")
async def read_task(id: int, path: str):
    from .utils import node_to_short_json
    from aiida.orm import load_node

    try:
        node = load_node(id)
        segments = path.split("/")
        ndata = node.workgraph_data["tasks"][segments[0]]
        ndata = deserialize_unsafe(ndata)
        executor = node.task_executors.get(segments[0], None)
        if len(segments) == 1:
            ndata["executor"] = executor if executor else {}
            content = node_to_short_json(id, ndata)
            return content
        else:
            if ndata["metadata"]["node_type"].upper() == "WORKGRAPH":
                graph_data = executor["graph_data"]
                ndata = graph_data["tasks"][segments[1]]
                for segment in segments[2:]:
                    ndata = ndata["executor"]["graph_data"]["tasks"][segment]
                content = node_to_short_json(None, ndata)
            elif ndata["metadata"]["node_type"].upper() == "MAP":
                map_info = node.task_map_info.get(segments[0])
                for child in map_info["children"]:
                    for prefix in map_info["prefix"]:
                        if f"{prefix}_{child}" == segments[1]:
                            ndata = deserialize_unsafe(
                                node.workgraph_data["tasks"][child]
                            )
                            executor = node.task_executors.get(child)
                            ndata["name"] = f"{prefix}_{child}"
                            ndata["executor"] = executor if executor else {}
                            break
                content = node_to_short_json(id, ndata)
            return content
    except KeyError as e:
        error_traceback = traceback.format_exc()  # Capture the full traceback
        print(error_traceback)
        raise HTTPException(
            status_code=404, detail=f"Workgraph {id}/{path} not found, {e}"
        )


@router.get("/api/workgraph/{id}/{path:path}")
async def read_sub_workgraph(id: int, path: str):
    """
    path is a string that contains everything after {id}/
    e.g. if the request is /api/workgraph/123/foo/bar/baz
    then path = "foo/bar/baz"
    """
    from aiida_workgraph.utils import workgraph_to_short_json, shallow_copy_nested_dict
    from aiida.orm import load_node

    try:
        node = load_node(id)
        segments = path.split("/")
        ndata = node.workgraph_data["tasks"][segments[0]]
        ndata = deserialize_unsafe(ndata)
        if ndata["metadata"]["node_type"].upper() == "WORKGRAPH":
            executor = node.task_executors.get(segments[0])
            graph_data = executor["graph_data"]
            for segment in segments[1:]:
                graph_data = graph_data["tasks"][segment]["executor"]["graph_data"]
        elif ndata["metadata"]["node_type"].upper() == "MAP":
            map_info = node.task_map_info.get(segments[0])
            graph_data = {"name": segments[-1], "uuid": "", "tasks": {}, "links": []}
            # copy tasks
            for child in map_info["children"]:
                child_data = deserialize_unsafe(node.workgraph_data["tasks"][child])
                for prefix in map_info["prefix"]:
                    new_data = shallow_copy_nested_dict(child_data)
                    new_data["name"] = f"{prefix}_{child}"
                    graph_data["tasks"][f"{prefix}_{child}"] = new_data
            # copy links
            for link in map_info["links"]:
                if (
                    link["from_node"] in map_info["children"]
                    and link["to_node"] in map_info["children"]
                ):
                    for prefix in map_info["prefix"]:
                        from_node = f"{prefix}_{link['from_node']}"
                        to_node = f"{prefix}_{link['to_node']}"
                        graph_data["links"].append(
                            {
                                "from_node": from_node,
                                "to_node": to_node,
                                "from_socket": link["from_socket"],
                                "to_socket": link["to_socket"],
                            }
                        )
        content = workgraph_to_short_json(graph_data)
        if content is None:
            print("No workgraph data found in the node.")
            return
        summary = {
            "table": [],
            "inputs": {},
            "outputs": {},
        }

        parent_workgraphs = [[node.process_label, id]] + segments
        content["summary"] = summary
        content["parent_workgraphs"] = parent_workgraphs
        content["processes_info"] = {}
        return content
    except KeyError as e:
        error_traceback = traceback.format_exc()  # Capture the full traceback
        print(error_traceback)
        raise HTTPException(
            status_code=404, detail=f"Workgraph {id}/{path} not found, {e}"
        )


@router.get("/api/workgraph/{id}")
async def read_workgraph(id: int):
    from .utils import (
        get_node_summary,
        get_node_inputs,
        get_node_outputs,
    )

    try:

        node = orm.load_node(id)

        content = node.workgraph_data_short
        if content is None:
            print("No workgraph data found in the node.")
            return
        summary = {
            "table": get_node_summary(node),
            "inputs": get_node_inputs(id),
            "outputs": get_node_outputs(id),
        }

        parent_workgraphs = get_parent_workgraphs(id)
        parent_workgraphs.reverse()
        content["summary"] = summary
        content["parent_workgraphs"] = parent_workgraphs
        content["processes_info"] = {}
        return content
    except KeyError as e:
        error_traceback = traceback.format_exc()  # Capture the full traceback
        print(error_traceback)
        raise HTTPException(status_code=404, detail=f"Workgraph {id} not found, {e}")


@router.get("/api/workgraph-state/{id}")
async def read_tasks_state(id: int, item_type: str = "task"):
    from aiida_workgraph.utils import get_processes_latest

    try:
        processes_info = get_processes_latest(id, item_type=item_type)
        return processes_info
    except KeyError as e:
        error_traceback = traceback.format_exc()  # Capture the full traceback
        print(error_traceback)
        raise HTTPException(status_code=404, detail=f"Workgraph {id} not found, {e}")


@router.get("/api/workgraph-logs/{id}")
async def read_workgraph_logs(id: int):
    from aiida.cmdline.utils.common import get_workchain_report

    try:
        node = orm.load_node(id)
        report = get_workchain_report(node, "REPORT")
        logs = report.splitlines()
        return logs
    except KeyError as e:
        error_traceback = traceback.format_exc()  # Capture the full traceback
        print(error_traceback)
        raise HTTPException(status_code=404, detail=f"Workgraph {id} not found, {e}")


# Route for pausing a workgraph item
@router.post("/api/workgraph/pause/{id}")
async def pause_workgraph(
    id: int,
):
    from aiida.engine.processes.control import pause_processes

    try:
        # Perform the pause action here
        node = orm.load_node(id)
        pause_processes([node])
        return {"message": f"Send message to pause workgraph {id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Route for playing a workgraph item
@router.post("/api/workgraph/play/{id}")
async def play_workgraph(
    id: int,
):
    from aiida.engine.processes.control import play_processes

    try:
        # Perform the play action here
        node = orm.load_node(id)
        play_processes([node])
        return {"message": f"Send message to play workgraph {id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Route for deleting a workgraph item
@router.delete("/api/workgraph/delete/{id}")
async def delete_workgraph(
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
                "message": f"Deleted workgraph {id}",
                "deleted_nodes": list(deleted_nodes),
            }
        else:
            message = f"Did not delete workgraph {id}"
            if dry_run:
                message += " [dry-run]"
            return {
                "deleted": False,
                "message": message,
                "deleted_nodes": list(deleted_nodes),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# General function to manage task actions
async def manage_task_action(action: str, id: int, tasks: List[str]):
    from aiida_workgraph.utils.control import pause_tasks, play_tasks, kill_tasks

    print(f"Performing {action} action on tasks {tasks} in workgraph {id}")
    try:

        if action == "pause":
            print(f"Pausing tasks {tasks}")
            _, msg = pause_tasks(id, tasks=tasks)
        elif action == "play":
            print(f"Playing tasks {tasks}")
            _, msg = play_tasks(id, tasks)
        elif action == "kill":
            print(f"Killing tasks {tasks}")
            _, msg = kill_tasks(id, tasks)
        else:
            raise HTTPException(status_code=400, detail="Unsupported action")

        return {"message": msg}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint for pausing tasks in a workgraph
@router.post("/api/workgraph/tasks/pause/{id}")
async def pause_workgraph_tasks(id: int, tasks: List[str] = None):
    return await manage_task_action("pause", id, tasks)


# Endpoint for playing tasks in a workgraph
@router.post("/api/workgraph/tasks/play/{id}")
async def play_workgraph_tasks(id: int, tasks: List[str] = None):
    return await manage_task_action("play", id, tasks)


# Endpoint for killing tasks in a workgraph
@router.post("/api/workgraph/tasks/kill/{id}")
async def kill_workgraph_tasks(id: int, tasks: List[str] = None):
    return await manage_task_action("kill", id, tasks)
