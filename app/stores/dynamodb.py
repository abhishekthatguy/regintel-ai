"""DynamoDB store — Phase 3 enterprise boundary (BRD: USECASE/CONVERSE/
TICKETS tables). Mirrors SQLiteStore's method surface so the swap is
config-only; every method raises until AWS table ARNs + credentials are
provided. Key design (when wired):
  CONVERSE:  pk=CONV#{conversation_id}, sk=META | MSG#{ts}#{message_id}
  TICKETS:   pk=EMP#{employee_id},      sk=TICKET#{ticket_id}
  USECASE:   pk=UC#{usecase_id},        sk=v{version} (+ ACTIVE pointer)
"""


class BackendNotConfiguredError(Exception):
    pass


class DynamoDBStore:
    def __init__(self, table_prefix: str = "", region: str = "", **_kwargs):
        self._ready = bool(table_prefix and region)
        self._table_prefix = table_prefix
        self._region = region

    def _unavailable(self, op: str):
        raise BackendNotConfiguredError(
            f"DynamoDBStore.{op}: set table_prefix/region and provide AWS "
            "credentials to enable the DynamoDB backend"
        )

    def init_schema(self):
        if not self._ready:
            self._unavailable("init_schema")

    def __getattr__(self, name: str):
        # Any conversation/ticket/feedback/chunk method hits this boundary.
        def _missing(*_args, **_kwargs):
            self._unavailable(name)

        return _missing
