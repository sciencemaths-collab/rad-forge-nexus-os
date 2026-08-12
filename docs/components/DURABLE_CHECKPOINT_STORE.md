# Component F: Durable Checkpoint Store

Status: TESTED | Store contract version: 1.0

SQLite checkpoints use WAL plus full synchronization and atomic `BEGIN IMMEDIATE`
compare-and-swap writes. Records bind run ID, graph digest, schema version, revision,
canonical bounded payload, and UTC save time. Resume can require matching graph and
schema contracts. Secret references and non-canonical payloads fail before writes.
