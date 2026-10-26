"""sqlite3's small cursor interface over Durable Objects' synchronous SQL API.

The caller MUST wrap each complete domain operation in storage.transactionSync.
App.db contexts then share that outer transaction, including nested reports.
"""
from contextlib import contextmanager

class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)

class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
    def __iter__(self): return self.rows
    def fetchone(self): return next(self.rows, None)
    def fetchall(self): return list(self.rows)

class Connection:
    def __init__(self, sql): self.sql = sql
    def execute(self, query, bindings=()):
        # Python buffers must cross FFI as ArrayBuffer, not as a PyProxy.
        from pyodide.ffi import to_js
        values = [to_js(v).buffer if isinstance(v, bytes) else v for v in bindings]
        cursor = self.sql.exec(query, *values)
        rows = cursor.toArray()
        if hasattr(rows, 'to_py'): rows = rows.to_py()
        return Cursor([Row(row) for row in rows])
    def executescript(self, query): return self.execute(query)
    def executemany(self, query, rows):
        for row in rows: self.execute(query, row)

@contextmanager
def database(connection):
    yield connection
