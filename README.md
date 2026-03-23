# Amazon Return Fraud Ring Detection System
### BEMM459 - Database Technologies for Business Analytics | University of Exeter | Group H

A polyglot persistence system that detects return fraud on an Amazon-like platform by combining **Microsoft SQL Server** (transactional records) with **Neo4j AuraDB** (graph-based relationship detection).

---

## Table of Contents

- [Project Overview](#project-overview)
- [Fraud Patterns Detected](#fraud-patterns-detected)
- [Repository Structure](#repository-structure)
- [Database Architecture](#database-architecture)
  - [SQL Server (Relational)](#sql-server-relational)
  - [Neo4j AuraDB (Graph)](#neo4j-auradb-graph)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Setup Steps](#setup-steps)
- [Running the System](#running-the-system)
- [Seeded Fraud Scenarios](#seeded-fraud-scenarios)
- [Operational Scenarios](#operational-scenarios)

---

## Project Overview

This system monitors customer orders and returns to automatically detect fraud. It uses two databases working together:

- **SQL Server** stores all structured business data like customers, orders, returns, refunds, and fraud alerts.
- **Neo4j** maps relationships between customers, devices, bank accounts, and phone numbers as a graph, making ring-based fraud patterns easy to spot.

When fraud is detected, a `FraudAlert` record is written to SQL Server and the relevant graph edges are created or updated in Neo4j. A fraud score of **≥ 5.0** triggers an alert automatically.

---

## Fraud Patterns Detected

| # | Pattern | How It Works |
|---|---|---|
| 1 | **Fraud Ring** | Multiple customer accounts share the same device fingerprint, bank reference, or delivery address |
| 2 | **Duplicate Phone** | Two or more customer accounts are registered with the same phone number |
| 3 | **Card Skimming** | The same bank card is used in two cities more than 100 miles apart within a 2-hour window (impossible travel) |
| 4 | **Suspect eCommerce** | Multiple accounts share the same device fingerprint or IP address |

A fifth behavioural signal which is **High Return Rate** (>50% of orders returned), is also tracked as an alert type in SQL.

---

## Repository Structure

```
├── ddl.sql                  # SQL Server schema — creates all 8 tables and indexes
├── dml.sql                  # Seed data - 500 customers with embedded fraud scenarios
├── schema.dbml              # Visual schema definition (paste into dbdiagram.io)
├── generate_data.py         # Script that generates dml.sql from scratch
├── seed_data.py             # Seeds Neo4j AuraDB with nodes, relationships, and constraints
├── neo4j_setup.cypher       # Standalone Cypher script for Neo4j schema setup
├── main.py                  # Main fraud detection application
├── erd.md                   # Entity Relationship Diagram (Mermaid)
└── neo4j_schema.md          # Neo4j graph schema and Cypher query reference
```

---

## Database Architecture

### SQL Server (Relational)

Eight tables store all transactional and operational data:

```
Analyst ──────────────────────────────► FraudAlert ◄─── Customer
                                                              │
                              ┌───────────────┬──────────────┤
                              ▼               ▼              ▼
                           Address          Order          Return
                                              │               │
                                              └───────────────► Refund
                                          (BankRef links
                                           Order → Refund)
```

**Key fraud signal columns:**

| Column | Table | Detects |
|---|---|---|
| `Phone` | Customer | Duplicate Phone |
| `DeviceFingerprint` | Customer | Suspect eCommerce / Fraud Ring |
| `IPAddress` | Customer | Suspect eCommerce |
| `Postcode` | Customer, Address | Fraud Ring geographic clustering |
| `BankRef` | Order, Refund | Fraud Ring, Skimming |
| `CardLastFour` | Order | Skimming |
| `OrderCity` | Order | Skimming (impossible travel) |

### Neo4j AuraDB (Graph)

The graph models shared attributes as **hub nodes** that customer nodes connect to. Two customers sharing a hub node is the fraud signal.

**Node labels:** `Customer`, `Device`, `BankAccount`, `Phone`, `Address`, `Location`, `FraudRing`

**Key relationships:**

| Relationship | Meaning |
|---|---|
| `USES_DEVICE` | Customer → Device fingerprint |
| `HAS_BANK` | Customer → BankAccount |
| `HAS_PHONE` | Customer → Phone number |
| `SHIPS_TO` | Customer → Address |
| `USED_IN` | BankAccount → Location (city) — enables skimming detection |
| `SHARES_*_WITH` | Direct Customer ↔ Customer links created on fraud detection |
| `MEMBER_OF` | Customer → FraudRing (created when a ring is confirmed) |

The `customerID` property on Neo4j `Customer` nodes matches the `CustomerID` primary key in SQL Server exactly, bridging both databases.

---

## Getting Started

### Prerequisites

- Python 3.9+
- [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Access to the University of Exeter SQL Server (`mcruebs04.isad.isadroot.ex.ac.uk`)
- A Neo4j AuraDB instance (free tier works)

Install Python dependencies:

```bash
pip install pyodbc neo4j
```

### Environment Variables

Set these before running to avoid hardcoding credentials:

```bash
export SQL_PASSWORD="your_sql_password"
export NEO4J_URI="neo4j+ssc://your-instance.databases.neo4j.io:7687"
export NEO4J_USERNAME="your_neo4j_username"
export NEO4J_PASSWORD="your_neo4j_password"
```

### Setup Steps

**1. Create the SQL Server schema**

Run `ddl.sql` against the target database. This drops and recreates all 8 tables and their indexes:

```bash
sqlcmd -S mcruebs04.isad.isadroot.ex.ac.uk -d BEMM459_2026_Group_H -U Group_H_2026 -i ddl.sql
```

**2. Load SQL seed data**

Run `dml.sql` to insert 500 customers and all embedded fraud scenarios:

```bash
sqlcmd -S mcruebs04.isad.isadroot.ex.ac.uk -d BEMM459_2026_Group_H -U Group_H_2026 -i dml.sql
```

Alternatively, regenerate `dml.sql` from scratch (useful if you want fresh random data while keeping the same fraud patterns):

```bash
python generate_data.py
```

**3. Seed the Neo4j graph**

Creates all constraints, indexes, nodes, and relationships in Neo4j AuraDB:

```bash
python seed_data.py
```

---

## Running the System

```bash
python main.py
```

The script connects to both databases on startup and runs through the three operational scenarios, printing results to the console.

---

## Seeded Fraud Scenarios

The dataset includes two examples of each fraud pattern, covering CustomerIDs 1–21. CustomerIDs 22–500 are clean, legitimate customers.

| Pattern | Customers | Detail |
|---|---|---|
| **Fraud Ring A** | 1 – 5 | Shared device `fp_ring_alpha_a1b2`, bank `BARC-9921-GBP`, postcode `EC1A 1BB` |
| **Fraud Ring B** | 6 – 9 | Shared device `fp_ring_gamma_c3d4`, bank `BARC-3344-GBP`, postcode `E1 6RF` |
| **Duplicate Phone A** | 10 & 11 | Both registered with `07700900999` |
| **Duplicate Phone B** | 12 & 13 | Both registered with `07700901234` |
| **Skimming A** | 14 | Card `BARC-7788-GBP` used in London at 09:00 and Edinburgh at 09:45 (45-minute gap) |
| **Skimming B** | 15 | Card `BARC-5566-GBP` used in Manchester at 10:00 and Bristol at 11:00 (60-minute gap) |
| **Suspect eCommerce A** | 16 – 18 | Shared device `fp_shared_ecom_a`, IP `85.10.20.30` |
| **Suspect eCommerce B** | 19 – 21 | Shared device `fp_shared_ecom_b`, IP `91.22.33.44` |

---

## Operational Scenarios

The system demonstrates three scenarios in `main.py`:

**Scenario 1 — Register a Return**
Inserts a new return into SQL Server, queries Neo4j for suspicious connections on the customer, and raises a `FraudAlert` if the fraud score meets the threshold (≥ 5.0).

**Scenario 2 — Detect Fraud Rings**
Traverses the Neo4j graph to find clusters of customers sharing both a device and a bank account. For each cluster of 3+ members, it pulls financial totals from SQL Server, calculates total ring exposure, writes `MEMBER_OF` edges in Neo4j, and creates `FRAUD_RING` alerts in SQL.

**Scenario 3 — Investigate a Customer**
Builds a full case file for a given customer by combining SQL transactional history with their Neo4j relationship map. Optionally runs a shortest-path query between two suspect customers to reveal the chain of shared attributes connecting them.
