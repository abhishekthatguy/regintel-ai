"""DynamoDB store — Phase 9 production boundary (BRD: USECASE/CONVERSE/
TICKETS tables). Mirrors SQLiteStore's method surface so the swap is
config-only via REGINTEL_STORE_BACKEND=dynamodb.

Tables (all PAY_PER_REQUEST, created by init_schema when absent):
  {prefix}-conversations
      pk=CONV#{conversation_id}
        sk=META                          conv attrs + gsi1pk=USER#{user_id},
                                         gsi1sk={updated_at}  (list by user)
        sk=MSG#{created_at}#{message_id} msg attrs + gsi2pk=MSGID#{message_id}
                                         (point lookup by message_id)
  {prefix}-tickets
      pk=EMP#{employee_id}  sk=PROFILE | TICKET#{ticket_id}
      pk=COUNTERS           sk=TICKET  (atomic seq → TCK-{1000+n})
  {prefix}-kb
      pk=DOC#{doc_id}       sk=META | CHUNK#{chunk_id}
  {prefix}-app
      pk=FEEDBACK           sk={created_at}#{feedback_id}
      pk=AUDIT              sk={created_at}#{uuid}     (query desc = latest first)
      pk=JOB#{job_id}       sk=META | FAIL#{created_at}#{doc_id}
      pk=JOBS               sk={started_at}#{job_id}   (job index, time-ordered)

Analytics methods aggregate scans in Python — same results as the SQL
group-bys at demo/pilot scale.
"""

import json
import logging
import uuid
from datetime import UTC, datetime

from app.schemas.conversation import Conversation, ConversationStatus, Message

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("open", "in_progress")


class BackendNotConfiguredError(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DynamoDBStore:
    def __init__(
        self,
        table_prefix: str = "",
        region: str = "",
        endpoint_url: str | None = None,
        resource=None,
        **_kwargs,
    ):
        self._table_prefix = table_prefix
        self._region = region
        self._endpoint_url = endpoint_url
        self._ddb = resource
        self._ready = bool(table_prefix)
        self._tables: dict = {}

    # --- plumbing -------------------------------------------------------

    def _resource(self):
        if self._ddb is None:
            import boto3

            self._ddb = boto3.resource(
                "dynamodb", region_name=self._region or "us-east-1",
                endpoint_url=self._endpoint_url,
            )
        return self._ddb

    def _unavailable(self, op: str):
        raise BackendNotConfiguredError(
            f"DynamoDBStore.{op}: set table_prefix and provide AWS "
            "credentials to enable the DynamoDB backend"
        )

    def _table(self, name: str):
        if not self._ready:
            self._unavailable("_table")
        if name not in self._tables:
            self._tables[name] = self._resource().Table(f"{self._table_prefix}-{name}")
        return self._tables[name]

    def _conv(self):
        return self._table("conversations")

    def _tickets(self):
        return self._table("tickets")

    def _kb(self):
        return self._table("kb")

    def _app(self):
        return self._table("app")

    @staticmethod
    def _scan_all(table, **kwargs) -> list[dict]:
        items: list[dict] = []
        while True:
            resp = table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            key = resp.get("LastEvaluatedKey")
            if not key:
                return items
            kwargs["ExclusiveStartKey"] = key

    @staticmethod
    def _query_all(table, **kwargs) -> list[dict]:
        items: list[dict] = []
        while True:
            resp = table.query(**kwargs)
            items.extend(resp.get("Items", []))
            key = resp.get("LastEvaluatedKey")
            if not key:
                return items
            kwargs["ExclusiveStartKey"] = key

    # --- lifecycle ------------------------------------------------------

    def init_schema(self) -> None:
        if not self._ready:
            self._unavailable("init_schema")
        ddb = self._resource()
        key_schema = [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ]
        base_attrs = [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ]
        billing = {"BillingMode": "PAY_PER_REQUEST"}
        conv_gsis = [
            {
                "IndexName": "by_user",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by_message",
                "KeySchema": [
                    {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ]
        specs = {
            "conversations": {
                "AttributeDefinitions": base_attrs
                + [
                    {"AttributeName": "gsi1pk", "AttributeType": "S"},
                    {"AttributeName": "gsi1sk", "AttributeType": "S"},
                    {"AttributeName": "gsi2pk", "AttributeType": "S"},
                    {"AttributeName": "gsi2sk", "AttributeType": "S"},
                ],
                "GlobalSecondaryIndexes": conv_gsis,
            },
            "tickets": {"AttributeDefinitions": base_attrs},
            "kb": {"AttributeDefinitions": base_attrs},
            "app": {"AttributeDefinitions": base_attrs},
        }
        for name, extra in specs.items():
            full = f"{self._table_prefix}-{name}"
            try:
                ddb.create_table(
                    TableName=full,
                    KeySchema=key_schema,
                    **extra,
                    **billing,
                ).wait_until_exists()
            except self._resource().meta.client.exceptions.ResourceInUseException:
                pass
        logger.info("dynamodb tables ready", extra={"action": "db_init"})

    def ping(self) -> bool:
        try:
            self._conv().load()
            return True
        except Exception:
            return False

    # --- conversations / messages ----------------------------------------

    def create_conversation(self, conversation: Conversation) -> Conversation:
        self._conv().put_item(
            Item={
                "pk": f"CONV#{conversation.conversation_id}",
                "sk": "META",
                "conversation_id": conversation.conversation_id,
                "user_id": conversation.user_id,
                "title": conversation.title,
                "usecase_id": conversation.usecase_id,
                "usecase_version": conversation.usecase_version,
                "status": conversation.status.value,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "gsi1pk": f"USER#{conversation.user_id}",
                "gsi1sk": conversation.updated_at.isoformat(),
            }
        )
        return conversation

    def add_message(self, message: Message) -> Message:
        conv_pk = f"CONV#{message.conversation_id}"
        created = message.created_at.isoformat()
        self._conv().put_item(
            Item={
                "pk": conv_pk,
                "sk": f"MSG#{created}#{message.message_id}",
                "message_id": message.message_id,
                "conversation_id": message.conversation_id,
                "role": message.role.value,
                "content": message.content,
                "citations_json": json.dumps(
                    [c.model_dump(mode="json") for c in message.citations]
                ),
                "usage_json": (
                    message.usage.model_dump_json() if message.usage else None
                ),
                "correlation_id": message.correlation_id,
                "created_at": created,
                "gsi2pk": f"MSGID#{message.message_id}",
                "gsi2sk": created,
            }
        )
        self._conv().update_item(
            Key={"pk": conv_pk, "sk": "META"},
            UpdateExpression="SET updated_at = :u, gsi1sk = :u",
            ExpressionAttributeValues={":u": created},
        )
        return message

    @staticmethod
    def _item_to_conversation(item: dict, messages: list[Message]) -> Conversation:
        return Conversation(
            conversation_id=item["conversation_id"],
            user_id=item["user_id"],
            title=item["title"],
            usecase_id=item["usecase_id"],
            usecase_version=int(item["usecase_version"]),
            status=ConversationStatus(item["status"]),
            messages=messages,
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    @staticmethod
    def _item_to_message(item: dict) -> Message:
        from app.schemas.agent import UsageSummary
        from app.schemas.conversation import Citation, MessageRole

        return Message(
            message_id=item["message_id"],
            conversation_id=item["conversation_id"],
            role=MessageRole(item["role"]),
            content=item["content"],
            citations=[
                Citation.model_validate(c)
                for c in json.loads(item.get("citations_json") or "[]")
            ],
            usage=(
                UsageSummary.model_validate(json.loads(item["usage_json"]))
                if item.get("usage_json")
                else None
            ),
            correlation_id=item.get("correlation_id"),
            created_at=item["created_at"],
        )

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            self._conv(),
            KeyConditionExpression=Key("pk").eq(f"CONV#{conversation_id}"),
        )
        meta = next((i for i in items if i["sk"] == "META"), None)
        if meta is None:
            return None
        messages = [
            self._item_to_message(i)
            for i in items
            if i["sk"].startswith("MSG#")
        ]
        messages.sort(key=lambda m: m.created_at)
        return self._item_to_conversation(meta, messages)

    def list_conversations(self, user_id: str) -> list[Conversation]:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            self._conv(),
            IndexName="by_user",
            KeyConditionExpression=Key("gsi1pk").eq(f"USER#{user_id}"),
            ScanIndexForward=False,
        )
        return [
            self._item_to_conversation(i, [])
            for i in items
            if i.get("status") == "active"
        ]

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        self._conv().update_item(
            Key={"pk": f"CONV#{conversation_id}", "sk": "META"},
            UpdateExpression="SET title = :t",
            ExpressionAttributeValues={":t": title},
        )

    def set_conversation_status(self, conversation_id: str, status: str) -> None:
        self._conv().update_item(
            Key={"pk": f"CONV#{conversation_id}", "sk": "META"},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
        )

    def get_message(self, message_id: str) -> Message | None:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            self._conv(),
            IndexName="by_message",
            KeyConditionExpression=Key("gsi2pk").eq(f"MSGID#{message_id}"),
        )
        return self._item_to_message(items[0]) if items else None

    # --- employees --------------------------------------------------------

    def get_employee(self, employee_id: str) -> dict | None:
        resp = self._tickets().get_item(
            Key={"pk": f"EMP#{employee_id}", "sk": "PROFILE"}
        )
        item = resp.get("Item")
        if not item:
            return None
        return {
            "employee_id": item["employee_id"],
            "name": item.get("name", ""),
            "department": item.get("department", ""),
            "email": item.get("email", ""),
            "roles": item.get("roles") or ["employee"],
        }

    def upsert_employee(self, employee: dict) -> None:
        self._tickets().put_item(
            Item={
                "pk": f"EMP#{employee['employee_id']}",
                "sk": "PROFILE",
                "employee_id": employee["employee_id"],
                "name": employee.get("name", ""),
                "department": employee.get("department", ""),
                "email": employee.get("email", ""),
                "roles": employee.get("roles", ["employee"]),
            }
        )

    # --- tickets ---------------------------------------------------------

    def _ticket_items(self, employee_id: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        return self._query_all(
            self._tickets(),
            KeyConditionExpression=Key("pk").eq(f"EMP#{employee_id}")
            & Key("sk").begins_with("TICKET#"),
        )

    @staticmethod
    def _item_to_ticket(item: dict) -> dict:
        return {
            k: item.get(k)
            for k in (
                "ticket_id", "employee_id", "category", "description",
                "status", "priority", "created_at", "updated_at",
            )
        }

    def list_tickets(self, employee_id: str, open_only: bool = False) -> list[dict]:
        tickets = [self._item_to_ticket(i) for i in self._ticket_items(employee_id)]
        if open_only:
            tickets = [t for t in tickets if t["status"] in OPEN_STATUSES]
        return tickets

    def find_duplicate_ticket(
        self, employee_id: str, category: str, idempotency_key: str | None = None
    ) -> dict | None:
        """An open ticket in the same category counts as a duplicate (FR-09)."""
        candidates = [
            t
            for t in self.list_tickets(employee_id)
            if t["category"] == category and t["status"] in OPEN_STATUSES
        ]
        return max(candidates, key=lambda t: t["created_at"]) if candidates else None

    def next_ticket_id(self) -> str:
        resp = self._tickets().update_item(
            Key={"pk": "COUNTERS", "sk": "TICKET"},
            UpdateExpression="ADD seq :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return f"TCK-{1000 + int(resp['Attributes']['seq'])}"

    def create_ticket(self, ticket: dict) -> dict:
        self._tickets().put_item(
            Item={
                "pk": f"EMP#{ticket['employee_id']}",
                "sk": f"TICKET#{ticket['ticket_id']}",
                **self._item_to_ticket(ticket),
            }
        )
        return ticket

    # --- feedback --------------------------------------------------------

    def add_feedback(self, feedback: dict) -> dict:
        self._app().put_item(
            Item={
                "pk": "FEEDBACK",
                "sk": f"{feedback['created_at']}#{feedback['feedback_id']}",
                **feedback,
            }
        )
        return feedback

    # --- chunk store / ingestion ------------------------------------------

    def document_checksum(self, doc_id: str) -> str | None:
        resp = self._kb().get_item(Key={"pk": f"DOC#{doc_id}", "sk": "META"})
        item = resp.get("Item")
        return item["checksum"] if item else None

    def replace_document_chunks(self, doc_id: str, chunks, vectors: dict, checksum: str) -> None:
        """Idempotent re-ingestion: delete stale chunks, insert fresh ones."""
        from boto3.dynamodb.conditions import Key

        now = _now()
        table = self._kb()
        stale = self._query_all(
            table,
            KeyConditionExpression=Key("pk").eq(f"DOC#{doc_id}"),
            ProjectionExpression="pk, sk",
        )
        if stale:
            # deletes flush first — BatchWriteItem can't delete+put the
            # same key in one batch
            with table.batch_writer() as batch:
                for item in stale:
                    batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        with table.batch_writer() as batch:
            batch.put_item(
                Item={
                    "pk": f"DOC#{doc_id}",
                    "sk": "META",
                    "doc_id": doc_id,
                    "checksum": checksum,
                    "source_system": chunks[0].source_system if chunks else "",
                    "version": chunks[0].version if chunks else "",
                    "ingested_at": now,
                }
            )
            for c in chunks:
                batch.put_item(
                    Item={
                        "pk": f"DOC#{doc_id}",
                        "sk": f"CHUNK#{c.chunk_id}",
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "title": c.title,
                        "section": c.section,
                        "text": c.text,
                        "department": c.department,
                        "acl_json": json.dumps(c.acl),
                        "version": c.version,
                        "source_system": c.source_system,
                        "source_ref": c.source_ref,
                        "source_url": c.source_url,
                        "vector_json": json.dumps(vectors.get(c.chunk_id, [])),
                        "created_at": now,
                    }
                )

    def _chunk_items(self) -> list[dict]:
        from boto3.dynamodb.conditions import Attr

        return self._scan_all(
            self._kb(),
            FilterExpression=Attr("sk").begins_with("CHUNK#"),
        )

    def all_chunks(self):
        from app.retrieval.corpus import Chunk

        return [
            Chunk(
                chunk_id=i["chunk_id"],
                document_id=i["document_id"],
                title=i["title"],
                section=i.get("section") or "",
                text=i["text"],
                department=i.get("department") or "",
                acl=json.loads(i.get("acl_json") or "[]"),
                version=i.get("version") or "1",
                source_system=i.get("source_system") or "local_files",
                source_ref=i.get("source_ref") or "",
                source_url=i.get("source_url") or "",
            )
            for i in self._chunk_items()
        ]

    def chunk_vectors(self) -> dict[str, list[float]]:
        return {
            i["chunk_id"]: json.loads(i["vector_json"])
            for i in self._chunk_items()
            if i.get("vector_json")
        }

    # --- ingestion jobs ---------------------------------------------------

    def create_ingestion_job(self, job: dict) -> None:
        sk = f"{job.get('started_at') or _now()}#{job['job_id']}"
        with self._app().batch_writer() as batch:
            batch.put_item(
                Item={
                    "pk": f"JOB#{job['job_id']}",
                    "sk": "META",
                    "job_id": job["job_id"],
                    "source": job["source"],
                    "status": job["status"],
                    "ingested": 0,
                    "failed": 0,
                    "started_at": job.get("started_at"),
                }
            )
            batch.put_item(
                Item={
                    "pk": "JOBS",
                    "sk": sk,
                    "job_id": job["job_id"],
                }
            )

    def finish_ingestion_job(
        self, job_id: str, status: str, ingested: int, failed: int, error: str | None = None
    ) -> None:
        self._app().update_item(
            Key={"pk": f"JOB#{job_id}", "sk": "META"},
            UpdateExpression=(
                "SET #st = :s, ingested = :i, failed = :f, "
                "#err = :e, finished_at = :t"
            ),
            ExpressionAttributeNames={"#st": "status", "#err": "error"},
            ExpressionAttributeValues={
                ":s": status, ":i": ingested, ":f": failed,
                ":e": error, ":t": _now(),
            },
        )

    def add_ingestion_failure(self, job_id: str, doc_id: str, error: str) -> None:
        self._app().put_item(
            Item={
                "pk": f"JOB#{job_id}",
                "sk": f"FAIL#{_now()}#{doc_id}",
                "job_id": job_id,
                "doc_id": doc_id,
                "error": error,
                "created_at": _now(),
            }
        )

    def get_ingestion_job(self, job_id: str) -> dict | None:
        resp = self._app().get_item(Key={"pk": f"JOB#{job_id}", "sk": "META"})
        item = resp.get("Item")
        if not item:
            return None
        return {k: v for k, v in item.items() if k not in ("pk", "sk")}

    def list_ingestion_jobs(self, limit: int = 20) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        pointers = self._query_all(
            self._app(),
            KeyConditionExpression=Key("pk").eq("JOBS"),
            ScanIndexForward=False,
            Limit=limit,
        )
        jobs = []
        for p in pointers:
            job = self.get_ingestion_job(p["job_id"])
            if job:
                jobs.append(job)
        return jobs

    def ingestion_failures(self, job_id: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            self._app(),
            KeyConditionExpression=Key("pk").eq(f"JOB#{job_id}")
            & Key("sk").begins_with("FAIL#"),
        )
        return [
            {"doc_id": i["doc_id"], "error": i["error"], "created_at": i["created_at"]}
            for i in items
        ]

    # --- audit -------------------------------------------------------------

    def add_audit_record(self, actor: str, action: str, outcome: str, detail: dict) -> None:
        self._app().put_item(
            Item={
                "pk": "AUDIT",
                "sk": f"{_now()}#{uuid.uuid4().hex[:8]}",
                "actor": actor,
                "action": action,
                "outcome": outcome,
                "detail_json": json.dumps(detail),
                "created_at": _now(),
            }
        )

    def list_audit_records(self, limit: int = 100) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            self._app(),
            KeyConditionExpression=Key("pk").eq("AUDIT"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [
            {
                "actor": i["actor"],
                "action": i["action"],
                "outcome": i["outcome"],
                "detail": json.loads(i.get("detail_json") or "{}"),
                "created_at": i["created_at"],
            }
            for i in items
        ]

    # --- analytics (Python aggregation over scans — SQL parity) -----------

    def _all_conv_meta(self) -> list[dict]:
        from boto3.dynamodb.conditions import Attr

        return self._scan_all(
            self._conv(), FilterExpression=Attr("sk").eq("META")
        )

    def _all_messages(self) -> list[dict]:
        from boto3.dynamodb.conditions import Attr

        return self._scan_all(
            self._conv(), FilterExpression=Attr("sk").begins_with("MSG#")
        )

    def _all_feedback(self) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        return self._query_all(
            self._app(), KeyConditionExpression=Key("pk").eq("FEEDBACK")
        )

    def _employee_departments(self) -> dict[str, str]:
        from boto3.dynamodb.conditions import Attr

        items = self._scan_all(
            self._tickets(), FilterExpression=Attr("sk").eq("PROFILE")
        )
        return {i["employee_id"]: i.get("department") or "unknown" for i in items}

    def analytics_summary(self) -> dict:
        convs = self._all_conv_meta()
        assistant = [m for m in self._all_messages() if m.get("role") == "assistant"]
        tokens = 0
        latency = []
        for m in assistant:
            usage = json.loads(m["usage_json"]) if m.get("usage_json") else {}
            tokens += usage.get("total_tokens") or 0
            if usage.get("latency_ms") is not None:
                latency.append(usage["latency_ms"])
        from boto3.dynamodb.conditions import Attr

        tickets = self._scan_all(
            self._tickets(), FilterExpression=Attr("sk").begins_with("TICKET#")
        )
        fb = self._all_feedback()
        return {
            "conversations": len(convs),
            "assistant_messages": len(assistant),
            "total_tokens": tokens,
            "avg_latency_ms": round(sum(latency) / len(latency), 1) if latency else 0,
            "tickets": len(tickets),
            "feedback_up": sum(1 for f in fb if f.get("rating") == "up"),
            "feedback_down": sum(1 for f in fb if f.get("rating") == "down"),
        }

    def analytics_by_usecase(self) -> list[dict]:
        convs = self._all_conv_meta()
        msgs = self._all_messages()
        counts: dict[str, int] = {}
        conv_usecase = {c["conversation_id"]: c["usecase_id"] for c in convs}
        for m in msgs:
            if m.get("role") == "assistant" and m["conversation_id"] in conv_usecase:
                uc = conv_usecase[m["conversation_id"]]
                counts[uc] = counts.get(uc, 0) + 1
        return [
            {
                "usecase_id": uc,
                "conversations": sum(1 for c in convs if c["usecase_id"] == uc),
                "messages": counts.get(uc, 0),
            }
            for uc in {c["usecase_id"] for c in convs}
        ]

    def analytics_daily(self, days: int = 14) -> list[dict]:
        counts: dict[str, int] = {}
        for m in self._all_messages():
            if m.get("role") == "assistant":
                day = m["created_at"][:10]
                counts[day] = counts.get(day, 0) + 1
        return [
            {"day": d, "messages": n}
            for d, n in sorted(counts.items(), reverse=True)[:days]
        ]

    def analytics_not_found(self, limit: int = 50) -> list[dict]:
        records = [
            r for r in self.list_audit_records(limit=500)
            if r["action"] == "knowledge_not_found"
        ][:limit]
        return [
            {
                "actor": r["actor"],
                "query": r["detail"].get("query", ""),
                "usecase": r["detail"].get("usecase", ""),
                "at": r["created_at"],
            }
            for r in records
        ]

    def analytics_by_department(self) -> list[dict]:
        """Cost attribution: usage grouped by the caller's department."""
        dept_map = self._employee_departments()
        convs = self._all_conv_meta()
        msgs = self._all_messages()
        conv_dept = {
            c["conversation_id"]: dept_map.get(c["user_id"], "unknown")
            for c in convs
        }
        conv_uc = {c["conversation_id"]: c for c in convs}
        agg: dict[str, dict] = {}
        for c in convs:
            dept = dept_map.get(c["user_id"], "unknown")
            agg.setdefault(dept, {"conversations": 0, "messages": 0, "tokens": 0, "cost_usd": 0.0})
            agg[dept]["conversations"] += 1
        for m in msgs:
            if m.get("role") != "assistant" or m["conversation_id"] not in conv_uc:
                continue
            dept = conv_dept[m["conversation_id"]]
            usage = json.loads(m["usage_json"]) if m.get("usage_json") else {}
            agg[dept]["messages"] += 1
            agg[dept]["tokens"] += usage.get("total_tokens") or 0
            agg[dept]["cost_usd"] += usage.get("estimated_cost_usd") or 0
        return [
            {
                "department": dept,
                "conversations": v["conversations"],
                "messages": v["messages"],
                "tokens": v["tokens"],
                "cost_usd": round(v["cost_usd"], 6),
            }
            for dept, v in agg.items()
        ]

    def analytics_funnel(self) -> dict:
        convs = self._all_conv_meta()
        msgs = self._all_messages()
        return {
            "users": len({c["user_id"] for c in convs}),
            "conversations": len(convs),
            "user_messages": sum(1 for m in msgs if m.get("role") == "user"),
            "feedback": len(self._all_feedback()),
        }

    def analytics_unmet_needs(self, limit: int = 10) -> list[dict]:
        """Cluster not-found queries by shared dominant term — the content-gap
        signal for knowledge managers."""
        queries = [r["query"].lower() for r in self.analytics_not_found(limit=200)]
        stop = {
            "the", "a", "an", "how", "do", "i", "to", "is", "what", "my", "can",
            "for", "of", "in", "on", "and", "me", "it", "does", "are", "there",
            "get", "you", "we", "this", "that", "when", "where", "why",
        }
        clusters: dict[str, list[str]] = {}
        for q in queries:
            terms = [t for t in q.split() if t not in stop and len(t) > 3]
            for t in terms:
                clusters.setdefault(t, []).append(q)
        ranked = sorted(
            (
                {"term": t, "count": len(qs), "sample_queries": sorted(set(qs))[:3]}
                for t, qs in clusters.items()
            ),
            key=lambda c: -c["count"],
        )
        return [c for c in ranked if c["count"] > 1][:limit]

    def department_documents(self, department: str) -> list[dict]:
        """Distinct documents carrying this department's metadata."""
        seen: dict[str, dict] = {}
        for i in self._chunk_items():
            if i.get("department") != department:
                continue
            seen.setdefault(
                i["document_id"],
                {
                    "doc_id": i["document_id"],
                    "title": i["title"],
                    "department": i["department"],
                    "acl": i.get("acl_json"),
                    "version": i.get("version"),
                    "source_system": i.get("source_system"),
                },
            )
        return [seen[d] for d in sorted(seen)]

    def usecase_usage(self, usecase_id: str) -> dict:
        convs = [c for c in self._all_conv_meta() if c["usecase_id"] == usecase_id]
        conv_ids = {c["conversation_id"] for c in convs}
        messages = sum(
            1
            for m in self._all_messages()
            if m.get("role") == "assistant" and m["conversation_id"] in conv_ids
        )
        return {"conversations": len(convs), "messages": messages}

    def analytics_feedback_recent(self, limit: int = 20) -> list[dict]:
        fb = sorted(
            self._all_feedback(), key=lambda f: f.get("created_at", ""), reverse=True
        )[:limit]
        return [
            {
                "rating": f.get("rating"),
                "reason": f.get("reason"),
                "comment": f.get("comment"),
                "created_at": f.get("created_at"),
            }
            for f in fb
        ]
