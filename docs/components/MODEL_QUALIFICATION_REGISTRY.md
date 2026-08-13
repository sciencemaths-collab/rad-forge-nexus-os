# Component AP: Model Qualification Registry

The registry is an append-preserving SQLite boundary for Phase AO qualifications. It
recomputes Phase AJ and AO digests on registration and read, atomically supersedes an
older exact model binding, and records irreversible revocation without deleting history.

The store uses WAL and full synchronous writes. All authorization queries bind provider,
model, adapter version, requested proposal use, and UTC time. Database ownership remains
outside the trust boundary; corrupted rows fail closed.
