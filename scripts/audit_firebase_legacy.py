#!/usr/bin/env python3
"""Build a read-only Firebase legacy-state audit from local JSON snapshots.

This program has no network client and cannot write to Firebase. It only reads the
six exported JSON branches supplied with --snapshot-dir and writes local reports.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRANCHES = ("users", "groupRooms", "groupPendingRooms", "groups", "groupMembers", "userGroups")


def slug(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", text.lower()))


def canonical(value: Any, aliases: dict[str, str]) -> str:
    key = slug(value)
    seen: set[str] = set()
    while aliases.get(key) and key not in seen:
        seen.add(key)
        key = slug(aliases[key])
    return key


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_time(value: Any) -> tuple[float | None, str | None]:
    if isinstance(value, bool) or value in (None, ""):
        return None, None
    try:
        numeric = float(value)
        seconds = numeric / 1000 if numeric > 10_000_000_000 else numeric
        parsed = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
        return numeric, parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp() * 1000, parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        return None, None


def record_timestamp(record: dict[str, Any]) -> tuple[float | None, Any, str | None, str | None]:
    for field in ("updatedAt", "addedAt"):
        if field in record:
            order, formatted = iso_time(record.get(field))
            if order is not None:
                return order, record.get(field), field, formatted
    return None, None, None, None


def personal_status(record: dict[str, Any]) -> str:
    done, pending = record.get("done") is True, record.get("pending") is True
    if done and pending:
        return "done+pending"
    if done:
        return "done"
    if pending:
        return "pending"
    return "unknown"


def resolved_identity(raw_key: str, record: dict[str, Any], aliases: dict[str, str]) -> tuple[str, str, str | None]:
    key = slug(raw_key)
    if key in aliases:
        return canonical(key, aliases), "key-alias", key
    candidates = [("key", raw_key), ("id", record.get("id")), ("nombre", record.get("nombre")), ("roomName", record.get("roomName"))]
    for field, candidate in candidates:
        candidate_key = slug(candidate)
        if candidate_key in aliases and slug(aliases[candidate_key]) != candidate_key:
            return canonical(candidate_key, aliases), f"{field}-alias", candidate_key
    return canonical(key, aliases), "raw-key", None


def choose_winner(entries: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    dated = [entry for entry in entries if entry["timestampOrder"] is not None]
    if dated:
        newest = max(entry["timestampOrder"] for entry in dated)
        candidates = [entry for entry in dated if entry["timestampOrder"] == newest]
        basis = f"timestamp fiable más reciente ({candidates[0]['timestampIso']})"
        status_tiebreak = len(candidates) > 1
    else:
        candidates = list(entries)
        basis = "sin timestamp fiable"
        status_tiebreak = True
    done = [entry for entry in candidates if entry["state"] == "done"]
    if done and status_tiebreak:
        candidates = done
        basis += "; done prevalece ante empate o ausencia de fecha"
    candidates.sort(key=lambda item: (item["key"] != item["canonicalKey"], item["path"]))
    winner = candidates[0]
    if len(candidates) > 1:
        basis += "; desempate determinista favoreciendo la clave canónica"
    return winner, basis


def merged_personal_record(entries: list[dict[str, Any]], winner: dict[str, Any], canonical_key: str, canonical_name: str) -> dict[str, Any]:
    ordered = sorted(entries, key=lambda item: (item["timestampOrder"] is not None, item["timestampOrder"] or 0, item["state"] == "done", item["key"]))
    value: dict[str, Any] = {}
    for entry in ordered:
        value.update(entry["record"])
    value.update(winner["record"])
    value["id"] = canonical_key
    if canonical_name:
        value["nombre"] = canonical_name
    value["done"] = winner["state"] == "done"
    value["pending"] = winner["state"] == "pending"
    if not value["done"]:
        value.pop("completedMinutes", None)
    return value


def merged_group_record(entries: list[dict[str, Any]], winner: dict[str, Any], canonical_name: str) -> dict[str, Any]:
    ordered = sorted(entries, key=lambda item: (item["timestampOrder"] is not None, item["timestampOrder"] or 0, item["state"] == "done", item["key"]))
    value: dict[str, Any] = {}
    for entry in ordered:
        value.update(entry["record"])
    value.update(winner["record"])
    if canonical_name:
        value["roomName"] = canonical_name
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    snapshots = {name: load_json(args.snapshot_dir / f"{name}.json") or {} for name in BRANCHES}
    snapshot_hashes = {name: file_hash(args.snapshot_dir / f"{name}.json") for name in BRANCHES}
    catalog = load_json(ROOT / "catalog.json").get("catalogo", [])
    alias_config = load_json(ROOT / "room_aliases.json")

    catalog_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for room in catalog:
        catalog_by_key[slug(room.get("id") or room.get("nombre"))].append(room)

    aliases = {slug(source): slug(target) for source, target in alias_config.get("aliases", {}).items() if slug(source) and slug(target)}
    known_alias_rows: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source, target in aliases.items():
        if source != canonical(target, aliases):
            known_alias_rows[(source, canonical(target, aliases))].add("aliases")
    for target, metadata in alias_config.get("rooms", {}).items():
        target_key = slug(target)
        aliases[target_key] = target_key
        for human_alias in metadata.get("aliases", []):
            alias_key = slug(human_alias)
            if alias_key:
                aliases[alias_key] = target_key
                if alias_key != target_key:
                    known_alias_rows[(alias_key, target_key)].add("rooms.aliases")

    def catalog_meta(canonical_key: str) -> dict[str, Any]:
        matches = catalog_by_key.get(canonical_key, [])
        metadata = alias_config.get("rooms", {}).get(canonical_key, {})
        return {
            "canonicalKey": canonical_key,
            "catalogId": matches[0].get("id") if len(matches) == 1 else None,
            "canonicalName": (matches[0].get("nombre") if len(matches) == 1 else None) or metadata.get("canonical_name") or canonical_key,
            "catalogMatches": len(matches),
        }

    uids = sorted(snapshots["users"])
    user_labels = {uid: f"user-{index:02d}-{hashlib.sha256(uid.encode()).hexdigest()[:8]}" for index, uid in enumerate(uids, 1)}
    indexed_group_ids = {
        gid
        for user_indexes in snapshots["userGroups"].values()
        for gid in (user_indexes or {})
    }
    all_group_ids = sorted(set(snapshots["groups"]) | set(snapshots["groupMembers"]) | indexed_group_ids | set(snapshots["groupRooms"]) | set(snapshots["groupPendingRooms"]))
    group_labels = {gid: f"group-{index:02d}-{hashlib.sha256(gid.encode()).hexdigest()[:8]}" for index, gid in enumerate(all_group_ids, 1)}

    duplicate_cases: list[dict[str, Any]] = []
    manual_cases: list[dict[str, Any]] = []
    unmatched_states: list[dict[str, Any]] = []
    subject_summary: dict[str, dict[str, Any]] = {}

    def public_entry(path: str, key: str, canonical_key: str, record: dict[str, Any], state_value: str, resolution: str, matched_alias: str | None) -> dict[str, Any]:
        order, raw_timestamp, timestamp_field, timestamp_iso = record_timestamp(record)
        return {
            "path": path, "key": key, "canonicalKey": canonical_key, "state": state_value,
            "timestamp": raw_timestamp, "timestampField": timestamp_field, "timestampIso": timestamp_iso,
            "timestampOrder": order, "resolution": resolution, "matchedAlias": matched_alias,
            "record": record,
        }

    for uid, user in snapshots["users"].items():
        raw_states = (user or {}).get("roomStates") or {}
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw_key, record in raw_states.items():
            if not isinstance(record, dict):
                unmatched_states.append({"scope": "user", "subject": user_labels[uid], "path": f"users/{uid}/roomStates/{raw_key}", "reason": "registro no objeto"})
                continue
            identity, resolution, matched = resolved_identity(raw_key, record, aliases)
            entry = public_entry(f"users/{uid}/roomStates/{raw_key}", raw_key, identity, record, personal_status(record), resolution, matched)
            grouped[identity].append(entry)
            if catalog_meta(identity)["catalogMatches"] != 1:
                unmatched_states.append({"scope": "user", "subject": user_labels[uid], "path": entry["path"], "canonicalKey": identity, "reason": "sin correspondencia única en catálogo"})
        for identity, entries in grouped.items():
            if len(entries) < 2:
                continue
            meta = catalog_meta(identity)
            explicit = any(entry["resolution"] != "raw-key" for entry in entries)
            states = {entry["state"] for entry in entries}
            winner, basis = choose_winner(entries)
            safe = meta["catalogMatches"] == 1 and explicit and states <= {"done", "pending"}
            target_path = f"users/{uid}/roomStates/{identity}"
            proposed_value = merged_personal_record(entries, winner, identity, meta["canonicalName"])
            deletes = sorted(entry["path"] for entry in entries if entry["path"] != target_path)
            target_existing = next((entry for entry in entries if entry["path"] == target_path), None)
            target_action = "update" if target_existing and target_existing["record"] != proposed_value else ("create" if not target_existing else "keep")
            case = {
                "caseId": f"personal-{len(duplicate_cases)+1:03d}", "scope": "personal", "subject": user_labels[uid],
                "subjectId": uid, **meta, "current": entries, "contradiction": "done" in states and "pending" in states,
                "proposed": {"state": winner["state"], "targetPath": target_path, "value": proposed_value, "winnerPath": winner["path"], "reason": basis},
                "conceptualDiff": {"delete": deletes, "targetAction": target_action, "targetPath": target_path},
                "safeAutomatic": safe, "manualReason": None if safe else "identidad/estado sin correspondencia inequívoca",
            }
            duplicate_cases.append(case)
            if not safe:
                manual_cases.append(case)

    # Group identity is evaluated across both branches, because done/pending is encoded by the path.
    for gid in all_group_ids:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for branch, state_value in (("groupRooms", "done"), ("groupPendingRooms", "pending")):
            for raw_key, record in (snapshots[branch].get(gid) or {}).items():
                if not isinstance(record, dict):
                    unmatched_states.append({"scope": "group", "subject": group_labels[gid], "path": f"{branch}/{gid}/{raw_key}", "reason": "registro no objeto"})
                    continue
                identity, resolution, matched = resolved_identity(raw_key, record, aliases)
                entry = public_entry(f"{branch}/{gid}/{raw_key}", raw_key, identity, record, state_value, resolution, matched)
                entry["branch"] = branch
                grouped[identity].append(entry)
                if catalog_meta(identity)["catalogMatches"] != 1:
                    unmatched_states.append({"scope": "group", "subject": group_labels[gid], "path": entry["path"], "canonicalKey": identity, "reason": "sin correspondencia única en catálogo"})
        for identity, entries in grouped.items():
            if len(entries) < 2:
                continue
            meta = catalog_meta(identity)
            explicit = any(entry["resolution"] != "raw-key" for entry in entries)
            states = {entry["state"] for entry in entries}
            winner, basis = choose_winner(entries)
            safe = meta["catalogMatches"] == 1 and explicit
            target_branch = "groupRooms" if winner["state"] == "done" else "groupPendingRooms"
            target_path = f"{target_branch}/{gid}/{identity}"
            proposed_value = merged_group_record(entries, winner, meta["canonicalName"])
            deletes = sorted(entry["path"] for entry in entries if entry["path"] != target_path)
            target_existing = next((entry for entry in entries if entry["path"] == target_path), None)
            target_action = "update" if target_existing and target_existing["record"] != proposed_value else ("create" if not target_existing else "keep")
            case = {
                "caseId": f"group-{len(duplicate_cases)+1:03d}", "scope": "group", "subject": group_labels[gid],
                "subjectId": gid, "groupName": (snapshots["groups"].get(gid) or {}).get("name"), **meta,
                "current": entries, "contradiction": "done" in states and "pending" in states,
                "withinBranchDuplicate": any(sum(entry.get("branch") == branch for entry in entries) > 1 for branch in ("groupRooms", "groupPendingRooms")),
                "proposed": {"state": winner["state"], "targetPath": target_path, "value": proposed_value, "winnerPath": winner["path"], "reason": basis},
                "conceptualDiff": {"delete": deletes, "targetAction": target_action, "targetPath": target_path},
                "safeAutomatic": safe, "manualReason": None if safe else "identidad sin correspondencia inequívoca",
            }
            duplicate_cases.append(case)
            if not safe:
                manual_cases.append(case)

    group_inconsistencies: list[dict[str, Any]] = []
    groups, members, indexes = snapshots["groups"], snapshots["groupMembers"], snapshots["userGroups"]
    for gid, group in groups.items():
        owner = (group or {}).get("ownerUid")
        owner_member = (members.get(gid) or {}).get(owner) if owner else None
        if not owner or not owner_member or owner_member.get("role") != "owner" or owner_member.get("status") != "active":
            active_owners = [uid for uid, value in (members.get(gid) or {}).items() if (value or {}).get("role") == "owner" and (value or {}).get("status") == "active"]
            group_inconsistencies.append({
                "type": "group-owner", "group": group_labels.get(gid, gid), "groupId": gid,
                "groupName": (group or {}).get("name"), "ownerUid": owner,
                "ownerSubject": user_labels.get(owner, "external-" + hashlib.sha256(str(owner).encode()).hexdigest()[:8]) if owner else None,
                "ownerMemberRole": (owner_member or {}).get("role"), "ownerMemberStatus": (owner_member or {}).get("status"),
                "activeOwnerCount": len(active_owners),
                "detail": "ownerUid no corresponde a un miembro owner activo",
            })
    for gid, group_members in members.items():
        if gid not in groups:
            group_inconsistencies.append({"type": "orphan-groupMembers", "group": group_labels.get(gid, gid), "groupId": gid, "detail": "miembros sin metadatos de grupo"})
        for uid, membership in (group_members or {}).items():
            reverse = (indexes.get(uid) or {}).get(gid)
            if not reverse:
                group_inconsistencies.append({"type": "missing-userGroups", "group": group_labels.get(gid, gid), "groupId": gid, "user": user_labels.get(uid, "external-" + hashlib.sha256(uid.encode()).hexdigest()[:8]), "uid": uid, "detail": "miembro sin índice inverso"})
            elif reverse.get("role") != membership.get("role") or reverse.get("status") != membership.get("status"):
                group_inconsistencies.append({"type": "membership-mismatch", "group": group_labels.get(gid, gid), "groupId": gid, "user": user_labels.get(uid, "external-" + hashlib.sha256(uid.encode()).hexdigest()[:8]), "uid": uid, "detail": "rol/estado difiere entre groupMembers y userGroups"})
    for uid, user_indexes in indexes.items():
        for gid in (user_indexes or {}):
            if gid not in groups:
                group_inconsistencies.append({"type": "orphan-userGroups", "group": group_labels.get(gid, gid), "groupId": gid, "user": user_labels.get(uid, "external-" + hashlib.sha256(uid.encode()).hexdigest()[:8]), "uid": uid, "detail": "índice apunta a grupo inexistente"})
            if uid not in (members.get(gid) or {}):
                group_inconsistencies.append({"type": "orphan-userGroups", "group": group_labels.get(gid, gid), "groupId": gid, "user": user_labels.get(uid, "external-" + hashlib.sha256(uid.encode()).hexdigest()[:8]), "uid": uid, "detail": "índice sin miembro correspondiente"})
    for branch in ("groupRooms", "groupPendingRooms"):
        for gid, room_records in snapshots[branch].items():
            if gid not in groups:
                group_inconsistencies.append({"type": "orphan-group-state", "group": group_labels.get(gid, gid), "groupId": gid, "detail": f"{branch} apunta a grupo inexistente"})
            active_members = {uid for uid, value in (members.get(gid) or {}).items() if (value or {}).get("status") == "active"}
            for key, record in (room_records or {}).items():
                if isinstance(record, dict) and record.get("addedBy") not in active_members:
                    group_inconsistencies.append({"type": "state-addedBy", "group": group_labels.get(gid, gid), "groupId": gid, "path": f"{branch}/{gid}/{key}", "detail": "addedBy no es miembro activo actual"})

    editorial_alias_inconsistencies: list[dict[str, Any]] = []
    for target, metadata in alias_config.get("rooms", {}).items():
        target_key = slug(target)
        matches = catalog_by_key.get(target_key, [])
        if len(matches) != 1:
            continue
        catalog_room = matches[0]
        differences = []
        if metadata.get("canonical_name") and slug(metadata["canonical_name"]) != slug(catalog_room.get("nombre")):
            differences.append(f"nombre alias «{metadata['canonical_name']}» frente a catálogo «{catalog_room.get('nombre')}»")
        if metadata.get("canonical_company") and slug(metadata["canonical_company"]) != slug(catalog_room.get("empresa")):
            differences.append(f"empresa alias «{metadata['canonical_company']}» frente a catálogo «{catalog_room.get('empresa')}»")
        if differences:
            editorial_alias_inconsistencies.append({
                "type": "alias-metadata-mismatch", "canonicalKey": target_key,
                "catalogId": catalog_room.get("id"), "detail": "; ".join(differences),
            })

    alias_rows = []
    alias_target_problems = []
    for (alias_key, target_key), sources in sorted(known_alias_rows.items()):
        meta = catalog_meta(target_key)
        row = {"alias": alias_key, "canonicalKey": target_key, "catalogId": meta["catalogId"], "canonicalName": meta["canonicalName"], "sources": sorted(sources), "catalogMatches": meta["catalogMatches"]}
        alias_rows.append(row)
        if meta["catalogMatches"] != 1:
            alias_target_problems.append(row)

    affected_users = sorted({case["subject"] for case in duplicate_cases if case["scope"] == "personal"})
    affected_groups = sorted({case["subject"] for case in duplicate_cases if case["scope"] == "group"})
    distinct_rooms = sorted({case["canonicalKey"] for case in duplicate_cases})
    contradictions = [case for case in duplicate_cases if case["contradiction"]]
    unmatched_grouped: dict[str, dict[str, Any]] = {}
    for item in unmatched_states:
        key = item.get("canonicalKey") or "(sin clave)"
        bucket = unmatched_grouped.setdefault(key, {"canonicalKey": key, "occurrences": 0, "scopes": set(), "subjects": set()})
        bucket["occurrences"] += 1
        bucket["scopes"].add(item.get("scope"))
        bucket["subjects"].add(item.get("subject"))
    unmatched_summary = [
        {**item, "scopes": sorted(item["scopes"]), "subjects": sorted(item["subjects"])}
        for _, item in sorted(unmatched_grouped.items())
    ]
    delete_paths = sorted({path for case in duplicate_cases if case["safeAutomatic"] for path in case["conceptualDiff"]["delete"]})
    creates = [case for case in duplicate_cases if case["safeAutomatic"] and case["conceptualDiff"]["targetAction"] == "create"]
    updates = [case for case in duplicate_cases if case["safeAutomatic"] and case["conceptualDiff"]["targetAction"] == "update"]
    keeps = [case for case in duplicate_cases if case["safeAutomatic"] and case["conceptualDiff"]["targetAction"] == "keep"]

    for subject in sorted(set(affected_users + affected_groups)):
        cases = [case for case in duplicate_cases if case["subject"] == subject]
        subject_summary[subject] = {
            "scope": cases[0]["scope"], "duplicateCases": len(cases),
            "contradictions": sum(case["contradiction"] for case in cases),
            "rooms": sorted({case["canonicalKey"] for case in cases}),
            "safeAutomatic": sum(case["safeAutomatic"] for case in cases),
            "manualReview": sum(not case["safeAutomatic"] for case in cases),
        }

    plan = {
        "meta": {
            "mode": "dry-run", "applyEnabled": False, "firebaseWritesPerformed": False,
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "project": "scapesrooms", "sensitive": True,
            "warning": "Private local audit. Contains exact UIDs/paths. Review manually; do not commit or apply directly.",
            "resolutionRules": [
                "latest reliable updatedAt/addedAt wins", "done wins ties or missing timestamps",
                "only explicit room_aliases.json/catalog identities are merged", "same display name alone never merges identities",
            ],
            "sourceSha256": snapshot_hashes,
        },
        "summary": {
            "personalStateRecords": sum(len((user or {}).get("roomStates") or {}) for user in snapshots["users"].values()),
            "groupStateRecords": sum(len(records or {}) for branch in ("groupRooms", "groupPendingRooms") for records in snapshots[branch].values()),
            "duplicateCases": len(duplicate_cases), "personalDuplicateCases": sum(case["scope"] == "personal" for case in duplicate_cases),
            "groupDuplicateCases": sum(case["scope"] == "group" for case in duplicate_cases),
            "withinGroupBranchDuplicates": sum(case.get("withinBranchDuplicate", False) for case in duplicate_cases),
            "contradictions": len(contradictions), "distinctAffectedRooms": distinct_rooms,
            "usersAffected": len(affected_users), "groupsAffected": len(affected_groups),
            "safeAutomaticCases": sum(case["safeAutomatic"] for case in duplicate_cases), "manualReviewCases": len(manual_cases),
            "keysToDelete": len(delete_paths), "keysToCreate": len(creates), "keysToUpdate": len(updates), "canonicalKeysAlreadyCorrect": len(keeps),
            "groupMembershipInconsistencies": len(group_inconsistencies),
            "editorialAliasInconsistencies": len(editorial_alias_inconsistencies),
            "unmatchedStateReferences": len(unmatched_states),
            "knownAliasMappings": len(alias_rows), "aliasTargetsWithoutUniqueCatalogMatch": len(alias_target_problems),
        },
        "subjectSummary": subject_summary,
        "knownAliases": alias_rows,
        "duplicateCases": duplicate_cases,
        "conceptualOperations": [
            {
                "caseId": case["caseId"], "safeAutomatic": case["safeAutomatic"],
                "delete": [{"method": "DELETE", "path": path} for path in case["conceptualDiff"]["delete"]],
                "upsert": None if case["conceptualDiff"]["targetAction"] == "keep" else {
                    "method": "PUT", "action": case["conceptualDiff"]["targetAction"],
                    "path": case["proposed"]["targetPath"], "value": case["proposed"]["value"],
                },
            }
            for case in duplicate_cases
        ],
        "groupMembershipInconsistencies": group_inconsistencies,
        "editorialAliasInconsistencies": editorial_alias_inconsistencies,
        "unmatchedStateReferences": unmatched_states,
        "unmatchedStateSummary": unmatched_summary,
        "aliasTargetProblems": alias_target_problems,
    }

    def md_value(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "sí" if value else "no"
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Auditoría legacy de Firebase — dry-run",
        "",
        f"Generado: {plan['meta']['generatedAt']}. Proyecto: `scapesrooms`.",
        "",
        "Esta auditoría es de solo lectura. No se ejecutó ningún `PATCH`, `PUT`, `DELETE`, migración ni despliegue. El JSON asociado está en una carpeta ignorada porque contiene UID y rutas exactas.",
        "",
        "## Resumen ejecutivo",
        "",
        f"- Estados personales leídos: **{plan['summary']['personalStateRecords']}**.",
        f"- Estados de grupo leídos: **{plan['summary']['groupStateRecords']}**.",
        f"- Casos de identidad duplicada por ámbito: **{len(duplicate_cases)}** ({plan['summary']['personalDuplicateCases']} personales y {plan['summary']['groupDuplicateCases']} de grupo).",
        f"- Salas canónicas distintas afectadas: **{len(distinct_rooms)}**: {', '.join(f'`{room}`' for room in distinct_rooms) or 'ninguna'}.",
        f"- Contradicciones `done/pending`: **{len(contradictions)}**.",
        f"- Usuarios afectados: **{len(affected_users)}**. Grupos afectados: **{len(affected_groups)}**.",
        f"- Casos seguros para automatizar: **{plan['summary']['safeAutomaticCases']}**. Casos duplicados que requieren revisión manual: **{len(manual_cases)}**.",
        f"- Impacto propuesto: eliminar **{len(delete_paths)}** claves; crear **{len(creates)}** canónicas; actualizar **{len(updates)}** canónicas; conservar sin cambio **{len(keeps)}**.",
        f"- Inconsistencias reales de grupos/membresías: **{plan['summary']['groupMembershipInconsistencies']}**.",
        f"- Diferencias editoriales alias/catálogo: **{plan['summary']['editorialAliasInconsistencies']}**.",
        "",
        "## Identidades duplicadas y diff conceptual",
        "",
    ]
    for case in duplicate_cases:
        lines.extend([
            f"### {case['caseId']} · {case['canonicalName']} (`{case['canonicalKey']}`)",
            "",
            f"- Ámbito: **{case['scope']}**, sujeto **{case['subject']}**" + (f", grupo «{case.get('groupName')}»" if case.get("groupName") else "") + ".",
            f"- ID de catálogo: `{case.get('catalogId') or 'sin correspondencia única'}`.",
            f"- Contradicción: **{'sí' if case['contradiction'] else 'no'}**. Migración automática propuesta: **{'segura' if case['safeAutomatic'] else 'revisión manual'}**.",
            "",
            "| Clave actual | Rama/estado | Timestamp original | Fecha UTC | Resolución de identidad |",
            "|---|---|---:|---|---|",
        ])
        for entry in case["current"]:
            lines.append(f"| `{md_value(entry['key'])}` | {md_value(entry['state'])} | {md_value(entry['timestamp'])} | {md_value(entry['timestampIso'])} | {md_value(entry['resolution'])} |")
        lines.extend([
            "",
            f"**Después propuesto:** conservar `{case['proposed']['targetPath']}` como **{case['proposed']['state']}**. Motivo: {case['proposed']['reason']}.",
            "",
            f"- Eliminar: {', '.join(f'`{path}`' for path in case['conceptualDiff']['delete']) or 'ninguna clave'}.",
            f"- Clave canónica: **{case['conceptualDiff']['targetAction']}** en `{case['conceptualDiff']['targetPath']}`.",
            "",
        ])

    lines.extend(["## Contradicciones done/pending", ""])
    if contradictions:
        lines.extend(["| Caso | Sala | Sujeto | Estado propuesto | Motivo |", "|---|---|---|---|---|"])
        for case in contradictions:
            lines.append(f"| {case['caseId']} | {md_value(case['canonicalName'])} | {case['subject']} | {case['proposed']['state']} | {md_value(case['proposed']['reason'])} |")
    else:
        lines.append("No se detectaron contradicciones.")

    lines.extend(["", "## Resumen por usuario y grupo", "", "| Sujeto | Ámbito | Duplicados | Contradicciones | Salas | Automático | Manual |", "|---|---|---:|---:|---|---:|---:|"])
    for subject, summary in subject_summary.items():
        lines.append(f"| {subject} | {summary['scope']} | {summary['duplicateCases']} | {summary['contradictions']} | {', '.join(summary['rooms'])} | {summary['safeAutomatic']} | {summary['manualReview']} |")

    lines.extend(["", "## Alias legacy conocidos", "", "| Alias normalizado | ID canónico Firebase | ID del catálogo | Sala canónica | Fuente |", "|---|---|---|---|---|"])
    for row in alias_rows:
        lines.append(f"| `{row['alias']}` | `{row['canonicalKey']}` | `{row['catalogId'] or 'sin coincidencia'}` | {md_value(row['canonicalName'])} | {', '.join(row['sources'])} |")

    lines.extend(["", "## Inconsistencias de grupos y membresías", ""])
    if group_inconsistencies:
        for item in group_inconsistencies:
            context = item.get("group") or item.get("subject") or item.get("canonicalKey", "")
            if item.get("groupName"):
                context += f" («{item['groupName']}»)"
            detail = item["detail"]
            if item["type"] == "group-owner":
                detail += f"; el ownerUid figura como {item.get('ownerMemberRole')}/{item.get('ownerMemberStatus')} y hay {item.get('activeOwnerCount')} propietarios activos"
            lines.append(f"- **{item['type']}** · {context}: {detail}" + (f" (`{item['path']}`)" if item.get("path") else "") + ".")
    else:
        lines.append("No se detectaron incoherencias entre grupos, propietarios, miembros e índices, ni estados de grupo asociados a grupos inexistentes.")
    lines.extend(["", "## Diferencias editoriales entre alias y catálogo", ""])
    if editorial_alias_inconsistencies:
        for item in editorial_alias_inconsistencies:
            lines.append(f"- **{item['type']}** · `{item['canonicalKey']}`: {item['detail']}.")
    else:
        lines.append("No se detectaron diferencias entre los metadatos canónicos de alias y sus fichas únicas de catálogo.")
    lines.extend(["", f"Hay **{len(unmatched_states)}** referencias de estado sin correspondencia por ID canónico o alias explícito. No forman parte del plan automático; compartir nombre nunca basta para fusionarlas."])
    if unmatched_summary:
        lines.extend(["", "| Clave sin resolver | Apariciones | Ámbitos | Sujetos |", "|---|---:|---|---:|"])
        for item in unmatched_summary:
            lines.append(f"| `{item['canonicalKey']}` | {item['occurrences']} | {', '.join(item['scopes'])} | {len(item['subjects'])} |")
    if alias_target_problems:
        lines.append(f"Además, **{len(alias_target_problems)}** alias configurados apuntan a un destino sin coincidencia única en el catálogo y requieren revisión.")

    lines.extend([
        "", "## Impacto y límites", "",
        f"El diff conceptual automático contiene {len(delete_paths)} eliminaciones y {len(creates) + len(updates)} escrituras canónicas. Este informe no materializa un PATCH ejecutable y `applyEnabled` permanece en `false`.",
        "",
        "Los casos marcados seguros se basan en alias explícitos y una única ficha de catálogo. Las referencias sin correspondencia inequívoca, registros malformados y problemas estructurales quedan fuera de toda propuesta automática.",
        "",
        "## Fuentes y reproducibilidad", "",
    ])
    for name in BRANCHES:
        lines.append(f"- `/{name}`: SHA-256 `{snapshot_hashes[name]}`.")
    lines.extend(["- `catalog.json` y `room_aliases.json` del checkout local actual.", "- Regla temporal: `updatedAt`, después `addedAt`; fecha más reciente; ante empate o ausencia, `done`.", ""])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "firebase-legacy-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "FIREBASE_LEGACY_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"outputDir": str(args.output_dir), **plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
