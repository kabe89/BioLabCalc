# GxP Compliance & Cryptographic Audit Trails

In regulated life-sciences environments—governed by **FDA 21 CFR Part 11** (Electronic Records; Electronic Signatures), **EU Annex 11**, and **GxP standards (GLP, GMP, GCP)**—digital laboratory software must guarantee that electronic records are as trustworthy and reliable as paper records.

The BioLabCalc regulatory framework (`biolabcalc.eln.services.audit_service`, `biolabcalc.eln.schema.database`) implements an append-only, cryptographically verifiable audit architecture designed around the **ALCOA+** data integrity principles.

---

## 🏛️ Regulatory Compliance Framework

BioLabCalc complies with the core tenets of international pharmaceutical and bioprocess regulatory standards:

| ALCOA+ Principle | Regulatory Requirement | BioLabCalc Architectural Implementation |
| :--- | :--- | :--- |
| **Attributable** | Every action must identify the exact person who performed it. | Strict session binding, user ID attribution on every mutation, electronic signatures for approvals. |
| **Legible** | Records must remain readable throughout their retention lifecycle. | Human-readable JSON snapshots, standardized Markdown notebooks, and portable SQLite/PostgreSQL storage. |
| **Contemporaneous** | Recorded at the exact time the activity is executed. | Automated UTC ISO-8601 timestamps generated at the instant of event commitment. |
| **Original** | Primary source data or a true certified copy must be preserved. | SHA-256 Content-Addressed Storage (CAS) for raw instrument files with zero lossy compression. |
| **Accurate** | Error-free, truthful representation of the laboratory process. | Mandatory deviation logging, kinetic timer variance tracking, automated calculation engines. |
| **Complete** | Full audit trail of all changes without omission. | Append-only ledger recording before/after delta snapshots for every field mutation. |
| **Consistent** | Chronological order with no retroactive insertions. | Cryptographically linked SHA-256 hash blockchain preventing reordering or injection. |
| **Enduring** | Long-term archival without degradation or format obsolescence. | Standard SQL relational schemas, open JSONL ledgers, and zero proprietary lock-in. |
| **Available** | Readily accessible for regulatory inspection and review. | Instant audit trail export, filtering by entity/operator, and one-click mathematical integrity audits. |

---

## ⛓️ Cryptographically Chained Append-Only Ledger

The Audit Service (`biolabcalc.eln.services.audit_service`) maintains an append-only ledger structured identically to a cryptographic blockchain.

```
Genesis Event
┌──────────────────────────────────────┐
│ Event ID:   EVT-001                  │
│ Action:     CREATE_CAMPAIGN          │
│ Actor:      prof_franklin            │
│ Prev Hash:  000000000000000000...    │ (Genesis Hash: 64 zeros)
│ Event Hash: 4a8f9c102b3d4e5f...      │
└──────────────────┬───────────────────┘
                   │
                   ▼
Event 2
┌──────────────────────────────────────┐
│ Event ID:   EVT-002                  │
│ Action:     SOP_FORK                 │
│ Actor:      alice_r                  │
│ Prev Hash:  4a8f9c102b3d4e5f...      │ ◄── Matches Event 1 Hash
│ Event Hash: b7e21a943c8d0f12...      │
└──────────────────┬───────────────────┘
                   │
                   ▼
Event 3
┌──────────────────────────────────────┐
│ Event ID:   EVT-003                  │
│ Action:     TUBE_MOVE                │
│ Actor:      alice_r                  │
│ Prev Hash:  b7e21a943c8d0f12...      │ ◄── Matches Event 2 Hash
│ Event Hash: e3d905f8812ab4c7...      │
└──────────────────────────────────────┘
```

### Deterministic Hash Calculation
Every audit event generates a canonical JSON representation containing the event identifier, timestamp, entity type, target entity ID, action verb, actor attribution, prior state, new state, operational metadata, and the preceding event's hash:

```python
canonical_repr = json.dumps(
    {
        "event_id": event_id,
        "timestamp": timestamp,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "performed_by": performed_by,
        "previous_state": previous_state,
        "new_state": new_state,
        "metadata": metadata,
        "prev_hash": prev_hash,
    },
    sort_keys=True,
    default=str,
)
event_hash = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()
```

### Mathematical Tamper-Evidence Verification
Any unauthorized attempt to modify historical entries, alter tube volumes in the database, delete a failed experiment, or inject a backdated protocol immediately breaks the cryptographic hash chain:

```python
from biolabcalc.eln.services.audit_service import get_audit_service

audit_svc = get_audit_service()
is_valid, error_msg = audit_svc.verify_integrity()

if is_valid:
    print("✅ Audit Ledger Verified: Cryptographic integrity 100% intact.")
else:
    print(f"❌ AUDIT INTEGRITY FAILURE: {error_msg}")
```

If an adversary alters a single character in a past event:
1. Recomputing that event's SHA-256 hash produces a mismatch against its stored `event_hash`.
2. Even if the adversary updates that event's hash, all subsequent events fail verification because their `prev_hash` pointers no longer match.

---

## 📸 Before/After Delta State Snapshots

Under 21 CFR Part 11 §11.10(e), an audit trail must capture both the original value and the modified value whenever a record is altered. 

BioLabCalc serializes full state snapshots before and after every mutation:

```json
{
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "timestamp": "2026-11-12T14:45:00.123456Z",
  "entity_type": "tube",
  "entity_id": "TUBE-T7RNAP-001",
  "action": "TUBE_MOVE",
  "performed_by": "alice_r",
  "previous_state": {
    "box_id": "BOX-T7RNAP-01",
    "slot": "A1",
    "volume_ul": 1000.0,
    "concentration_mg_ml": 2.85
  },
  "new_state": {
    "box_id": "BOX-T7RNAP-02",
    "slot": "C4",
    "volume_ul": 950.0,
    "concentration_mg_ml": 2.85
  },
  "metadata": {
    "from_box": "BOX-T7RNAP-01",
    "from_slot": "A1",
    "to_box": "BOX-T7RNAP-02",
    "to_slot": "C4",
    "reason": "Consolidated into benchtop working box; 50 uL withdrawn for assay."
  },
  "prev_hash": "4a8f9c102b3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f",
  "event_hash": "b7e21a943c8d0f124a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f"
}
```

---

## 👥 Role-Based Access Control (RBAC)

BioLabCalc defines six distinct laboratory roles (`biolabcalc.eln.schema.ddl.sql`, `user_role` enum):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Laboratory Role Hierarchy                       │
├────────────────────────────┬───────────────────────────────────────────┤
│ Role                       │ Primary Authority & Permissions           │
├────────────────────────────┼───────────────────────────────────────────┤
│ `principal_investigator`   │ Master approval authority. Approves SOPs, │
│                            │ signs off campaigns, manages team roles.  │
├────────────────────────────┼───────────────────────────────────────────┤
│ `lab_manager`              │ Spatial facility administrator. Creates   │
│                            │ rooms, freezers, racks, and box layouts.  │
├────────────────────────────┼───────────────────────────────────────────┤
│ `active_researcher`        │ Full wet-lab execution. Creates daily     │
│                            │ entries, forks SOPs, places/moves tubes.  │
├────────────────────────────┼───────────────────────────────────────────┤
│ `rotation_student`         │ Supervised execution. Can check off steps │
│                            │ and log timepoints; entries require sign. │
├────────────────────────────┼───────────────────────────────────────────┤
│ `alumni`                   │ Read-only historical access. Preserves    │
│                            │ past records; cannot alter active states. │
├────────────────────────────┼───────────────────────────────────────────┤
│ `guest`                    │ Read-only showcase access for external    │
│                            │ peer-reviewers or auditors.               │
└────────────────────────────┴───────────────────────────────────────────┘
```

---

## ✍️ Electronic Signatures & Reason-for-Change

Under 21 CFR Part 11 Subpart C, electronic signatures must contain three specific pieces of information:
1. **Printed name of the signer** (`performed_by`, e.g. `Dr. Rosalind Franklin`).
2. **Date and time when signature was executed** (`timestamp` in UTC).
3. **Meaning associated with the signature** (e.g., review, approval, responsibility, or authorship).

### Reason-for-Change Enforcement
Any critical mutation—such as relocating a cryogenic tube, overriding an SOP parameter, or editing a notebook entry—mandates a human-provided justification string (`reason`). The API strictly rejects transactions where the reason string is empty or omitted.

---

## 🔗 Related Documentation
* [Electronic Lab Notebook (ELN)](Electronic-Lab-Notebook-(ELN)) — System architecture and persistence layer.
* [SOP & Protocol Management](SOP-&-Protocol-Management) — PI electronic sign-off lifecycle and protocol deviation logging.
* [Inventory & Freezer LIMS](Inventory-&-Freezer-LIMS) — Audited tube movements and cold-chain sample transfers.
