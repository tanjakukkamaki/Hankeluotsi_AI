import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Type

from pydantic import BaseModel

from hankeluotsi.schemas import ConceptPaper, ProjectIdea


SCHEMA_VERSION = 1


class ProjectState(str, Enum):
    CREATED = "created"
    CONCEPT_READY = "concept_ready"
    DRAFT_READY = "draft_ready"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class RepositoryError(ValueError):
    pass


class ProjectNotFound(RepositoryError):
    pass


class InvalidTransition(RepositoryError):
    pass


class ApprovedProjectLocked(RepositoryError):
    pass


class ExportNotApproved(RepositoryError):
    pass


class IdempotencyConflict(RepositoryError):
    pass


class StaleProjectError(RepositoryError):
    pass


class UnsupportedSchemaVersion(RepositoryError):
    pass


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    schema_version: int
    state: ProjectState
    created_at: str
    updated_at: str
    approved_at: str | None
    idea: ProjectIdea
    concept: ConceptPaper | None
    draft: dict[str, Any] | None
    deterministic_findings: list[dict[str, Any]] | None
    review: dict[str, Any] | None


class ProjectRepository:
    """Transactional SQLite persistence for one local project workflow."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _initialize(self) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('created', 'concept_ready', 'draft_ready', 'reviewed', 'approved')
                    ),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_at TEXT,
                    idea_json TEXT NOT NULL,
                    concept_json TEXT,
                    draft_json TEXT,
                    findings_json TEXT,
                    review_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    operation_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    operation_type TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS projects_updated_at_idx ON projects(updated_at DESC)"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _operation_id(operation_id: str) -> str:
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        return operation_id.strip()

    @staticmethod
    def _json_dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _payload_hash(cls, operation_type: str, payload: Any) -> str:
        serialized = cls._json_dump({"operation_type": operation_type, "payload": payload})
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _validated_json(model_type: Type[BaseModel], payload: BaseModel | dict[str, Any]) -> str:
        if not isinstance(model_type, type) or not issubclass(model_type, BaseModel):
            raise TypeError("model_type must be a Pydantic BaseModel class")
        raw_payload = payload.model_dump(mode="python") if isinstance(payload, BaseModel) else payload
        validated = model_type.model_validate(raw_payload)
        return json.dumps(validated.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    @classmethod
    def _validated_findings(cls, findings: list[dict[str, Any]]) -> str:
        if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
            raise TypeError("deterministic_findings must be a list of dictionaries")
        return cls._json_dump(findings)

    @staticmethod
    def _find_replay(
        connection: sqlite3.Connection,
        operation_id: str,
        operation_type: str,
        payload_hash: str,
        project_id: str | None = None,
    ) -> str | None:
        row = connection.execute(
            "SELECT project_id, operation_type, payload_hash FROM operations WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()
        if row is None:
            return None
        if (
            row["operation_type"] != operation_type
            or row["payload_hash"] != payload_hash
            or (project_id is not None and row["project_id"] != project_id)
        ):
            raise IdempotencyConflict("operation_id was already used for a different operation")
        return str(row["project_id"])

    @staticmethod
    def _record_operation(
        connection: sqlite3.Connection,
        operation_id: str,
        project_id: str,
        operation_type: str,
        payload_hash: str,
        timestamp: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO operations (operation_id, project_id, operation_type, payload_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (operation_id, project_id, operation_type, payload_hash, timestamp),
        )

    @staticmethod
    def _row(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if row is None:
            raise ProjectNotFound(f"project not found: {project_id}")
        return row

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> ProjectRecord:
        version = row["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise UnsupportedSchemaVersion(
                f"project schema version {version} is not supported (expected {SCHEMA_VERSION})"
            )
        try:
            state = ProjectState(row["state"])
        except ValueError as exc:
            raise RepositoryError(f"unsupported project state: {row['state']}") from exc

        idea = ProjectIdea.model_validate_json(row["idea_json"])
        concept = (
            ConceptPaper.model_validate_json(row["concept_json"])
            if row["concept_json"] is not None
            else None
        )
        return ProjectRecord(
            project_id=row["project_id"],
            schema_version=version,
            state=state,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            idea=idea,
            concept=concept,
            draft=json.loads(row["draft_json"]) if row["draft_json"] is not None else None,
            deterministic_findings=(
                json.loads(row["findings_json"]) if row["findings_json"] is not None else None
            ),
            review=json.loads(row["review_json"]) if row["review_json"] is not None else None,
        )

    def _load_with_connection(self, connection: sqlite3.Connection, project_id: str) -> ProjectRecord:
        return self._deserialize(self._row(connection, project_id))

    @staticmethod
    def _source_fingerprint(row: sqlite3.Row) -> str:
        fields = ("schema_version", "state", "updated_at", "approved_at", "idea_json", "concept_json",
                  "draft_json", "findings_json", "review_json")
        payload = json.dumps({field: row[field] for field in fields}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def source_fingerprint(self, project_id: str) -> str:
        return self.load_snapshot(project_id)[1]

    def load_snapshot(self, project_id: str) -> tuple[ProjectRecord, str]:
        """Read content and its CAS token from one row, never two different revisions."""
        with self._connection() as connection:
            row = self._row(connection, project_id)
            return self._deserialize(row), self._source_fingerprint(row)

    def operation_completed(self, project_id: str, operation_id: str, operation_type: str) -> bool:
        operation_id = self._operation_id(operation_id)
        with self._connection() as connection:
            row = connection.execute("SELECT project_id, operation_type FROM operations WHERE operation_id = ?",
                (operation_id,)).fetchone()
            if row is None:
                return False
            if row["project_id"] != project_id or row["operation_type"] != operation_type:
                raise IdempotencyConflict("operation ID already belongs to another project or action")
            return True

    def create_project(
        self,
        idea: ProjectIdea | dict[str, Any],
        *,
        operation_id: str,
    ) -> ProjectRecord:
        operation_id = self._operation_id(operation_id)
        idea_json = self._validated_json(ProjectIdea, idea)
        idea_data = json.loads(idea_json)
        payload_hash = self._payload_hash("create_project", idea_data)
        project_id = str(uuid.uuid4())
        timestamp = self._now()

        with self._transaction() as connection:
            replay_id = self._find_replay(
                connection, operation_id, "create_project", payload_hash
            )
            if replay_id is not None:
                return self._load_with_connection(connection, replay_id)
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, schema_version, state, created_at, updated_at, idea_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, SCHEMA_VERSION, ProjectState.CREATED.value, timestamp, timestamp, idea_json),
            )
            self._record_operation(
                connection, operation_id, project_id, "create_project", payload_hash, timestamp
            )
            return self._load_with_connection(connection, project_id)

    def save_idea(
        self,
        project_id: str,
        idea: ProjectIdea | dict[str, Any],
        *,
        operation_id: str,
    ) -> ProjectRecord:
        idea_json = self._validated_json(ProjectIdea, idea)
        return self._mutate(
            project_id,
            operation_id,
            "save_idea",
            json.loads(idea_json),
            {
                "idea_json": idea_json,
                "concept_json": None,
                "draft_json": None,
                "findings_json": None,
                "review_json": None,
                "approved_at": None,
            },
            ProjectState.CREATED,
            {
                ProjectState.CREATED,
                ProjectState.CONCEPT_READY,
                ProjectState.DRAFT_READY,
                ProjectState.REVIEWED,
            },
        )

    def save_concept(
        self,
        project_id: str,
        concept: ConceptPaper | dict[str, Any],
        *,
        operation_id: str,
    ) -> ProjectRecord:
        concept_json = self._validated_json(ConceptPaper, concept)
        return self._mutate(
            project_id,
            operation_id,
            "save_concept",
            json.loads(concept_json),
            {
                "concept_json": concept_json,
                "draft_json": None,
                "findings_json": None,
                "review_json": None,
                "approved_at": None,
            },
            ProjectState.CONCEPT_READY,
            {
                ProjectState.CREATED,
                ProjectState.CONCEPT_READY,
                ProjectState.DRAFT_READY,
                ProjectState.REVIEWED,
            },
        )

    def save_draft(
        self,
        project_id: str,
        draft: BaseModel | dict[str, Any],
        *,
        model_type: Type[BaseModel],
        operation_id: str,
        expected_source: str | None = None,
    ) -> ProjectRecord:
        draft_json = self._validated_json(model_type, draft)
        return self._mutate(
            project_id,
            operation_id,
            "save_draft",
            json.loads(draft_json),
            {
                "draft_json": draft_json,
                "findings_json": None,
                "review_json": None,
                "approved_at": None,
            },
            ProjectState.DRAFT_READY,
            {
                ProjectState.CONCEPT_READY,
                ProjectState.DRAFT_READY,
                ProjectState.REVIEWED,
            },
            required_columns=("concept_json",),
            expected_source=expected_source,
        )

    def save_review(
        self,
        project_id: str,
        review: BaseModel | dict[str, Any],
        *,
        model_type: Type[BaseModel],
        deterministic_findings: list[dict[str, Any]],
        operation_id: str,
        expected_source: str | None = None,
    ) -> ProjectRecord:
        review_json = self._validated_json(model_type, review)
        findings_json = self._validated_findings(deterministic_findings)
        payload = {
            "review": json.loads(review_json),
            "deterministic_findings": json.loads(findings_json),
        }
        return self._mutate(
            project_id,
            operation_id,
            "save_review",
            payload,
            {"review_json": review_json, "findings_json": findings_json, "approved_at": None},
            ProjectState.REVIEWED,
            {ProjectState.DRAFT_READY, ProjectState.REVIEWED},
            required_columns=("draft_json",),
            expected_source=expected_source,
        )

    def _mutate(
        self,
        project_id: str,
        operation_id: str,
        operation_type: str,
        payload: Any,
        updates: dict[str, str | None],
        next_state: ProjectState,
        allowed_states: set[ProjectState],
        required_columns: tuple[str, ...] = (),
        expected_source: str | None = None,
    ) -> ProjectRecord:
        operation_id = self._operation_id(operation_id)
        payload_hash = self._payload_hash(operation_type, payload)
        timestamp = self._now()

        with self._transaction() as connection:
            replay_id = self._find_replay(
                connection, operation_id, operation_type, payload_hash, project_id
            )
            if replay_id is not None:
                return self._load_with_connection(connection, replay_id)

            row = self._row(connection, project_id)
            self._deserialize(row)
            if expected_source is not None and self._source_fingerprint(row) != expected_source:
                raise StaleProjectError("project changed during this operation; reload and review the current record")
            state = ProjectState(row["state"])
            if state == ProjectState.APPROVED:
                raise ApprovedProjectLocked("approved projects are immutable")
            if state not in allowed_states:
                expected = ", ".join(sorted(item.value for item in allowed_states))
                raise InvalidTransition(
                    f"cannot {operation_type} while project is {state.value}; expected {expected}"
                )
            if any(row[column] is None for column in required_columns):
                raise InvalidTransition(f"cannot {operation_type} before its required earlier stage")

            assignments = ["state = ?", "updated_at = ?"]
            values: list[Any] = [next_state.value, timestamp]
            for column, value in updates.items():
                if column not in {
                    "idea_json",
                    "concept_json",
                    "draft_json",
                    "findings_json",
                    "review_json",
                    "approved_at",
                }:
                    raise ValueError(f"unsupported project update column: {column}")
                assignments.append(f"{column} = ?")
                values.append(value)
            values.append(project_id)
            connection.execute(
                f"UPDATE projects SET {', '.join(assignments)} WHERE project_id = ?", values
            )
            self._record_operation(
                connection, operation_id, project_id, operation_type, payload_hash, timestamp
            )
            return self._load_with_connection(connection, project_id)

    def approve_project(self, project_id: str, *, operation_id: str, expected_source: str | None = None) -> ProjectRecord:
        operation_id = self._operation_id(operation_id)
        operation_type = "approve_project"
        payload_hash = self._payload_hash(operation_type, {"approved": True})
        timestamp = self._now()

        with self._transaction() as connection:
            replay_id = self._find_replay(
                connection, operation_id, operation_type, payload_hash, project_id
            )
            if replay_id is not None:
                return self._load_with_connection(connection, replay_id)

            row = self._row(connection, project_id)
            self._deserialize(row)
            if expected_source is not None and self._source_fingerprint(row) != expected_source:
                raise StaleProjectError("project changed before approval; reload and review the current record")
            state = ProjectState(row["state"])
            if state != ProjectState.REVIEWED:
                if state == ProjectState.APPROVED:
                    raise ApprovedProjectLocked("approved projects are immutable")
                raise InvalidTransition("only reviewed projects can be approved")
            if row["draft_json"] is None or row["review_json"] is None:
                raise InvalidTransition("a draft and review are required before approval")

            connection.execute(
                "UPDATE projects SET state = ?, approved_at = ?, updated_at = ? WHERE project_id = ?",
                (ProjectState.APPROVED.value, timestamp, timestamp, project_id),
            )
            self._record_operation(
                connection, operation_id, project_id, operation_type, payload_hash, timestamp
            )
            return self._load_with_connection(connection, project_id)

    def load_project(self, project_id: str) -> ProjectRecord:
        with self._connection() as connection:
            return self._load_with_connection(connection, project_id)

    def list_projects(self) -> list[ProjectRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, project_id"
            ).fetchall()
            return [self._deserialize(row) for row in rows]

    def load_for_export(self, project_id: str) -> ProjectRecord:
        record = self.load_project(project_id)
        if record.state != ProjectState.APPROVED:
            raise ExportNotApproved("only human-approved projects can be exported")
        return record
