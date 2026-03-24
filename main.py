"""
main.py — Amazon Return Fraud Ring Detection System
BEMM459 — Database Technologies for Business Analytics
University of Exeter

Polyglot persistence: Microsoft SQL Server + Neo4j AuraDB

Four fraud patterns detected:
  1. Fraud Ring        — multiple accounts sharing address, bank, or device
  2. Duplicate Phone   — same phone number on two+ customer accounts
  3. Skimming          — same card used in distant cities within hours
  4. Suspect eCommerce — same device fingerprint or IP across accounts

Three operational scenarios:
  1. register_return()        — Insert return in SQL, check Neo4j for suspicious
                                connections, raise FraudAlert if warranted
  2. detect_fraud_ring()      — Find ring clusters in Neo4j, pull financial
                                evidence from SQL, calculate ring exposure,
                                write MEMBER_OF edges and SQL FraudAlerts
  3. investigate_customer()   — Full case file from SQL + Neo4j relationship map,
                                with optional shortest-path query between two suspects

Run:  python main.py
"""

import os
from datetime import datetime
from collections import defaultdict

import pyodbc
from neo4j import GraphDatabase

# ── Connection configuration ──────────────────────────────────────────────────
# Set environment variables before running, or replace the fallback strings.
SQL_SERVER   = 'mcruebs04.isad.isadroot.ex.ac.uk'
SQL_DATABASE = 'BEMM459_SSeli'
SQL_USERNAME = 'SSeli'
SQL_PASSWORD = os.getenv('SQL_PASSWORD', 'NtdY519*Yf')

NEO4J_URI      = os.getenv('NEO4J_URI',      'neo4j+ssc://78fe787f.databases.neo4j.io:7687')
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', '78fe787f')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'xmGh-UUzmmA0b8iHaJiN-H-tONUMsO4Oz5enBA2zSnA')

# FraudAlert is raised when the fraud score meets or exceeds this threshold
FRAUD_SCORE_THRESHOLD = 5.0

# A card used in two cities more than this many miles apart within the skimming
# time window is flagged as a skimming incident
SKIMMING_WINDOW_HOURS  = 2
SKIMMING_MIN_MILES     = 100   # London–Edinburgh ≈ 400 miles

# Minimum cluster size to constitute a fraud ring
RING_MIN_MEMBERS = 3


# ── Main class ────────────────────────────────────────────────────────────────
class FraudDetectionSystem:

    def __init__(self):
        self.sql   = self._connect_sql()
        self.neo4j = self._connect_neo4j()

    # ── Connections ───────────────────────────────────────────────────────────

    def _connect_sql(self):
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USERNAME};"
            f"PWD={SQL_PASSWORD};"
        )
        try:
            conn = pyodbc.connect(conn_str)
            print("[SQL]   Connected to SQL Server.")
            return conn
        except Exception as e:
            raise ConnectionError(f"[SQL]   Connection failed: {e}")

    def _connect_neo4j(self):
        try:
            driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )
            driver.verify_connectivity()
            print("[Neo4j] Connected.")
            return driver
        except Exception as e:
            raise ConnectionError(f"[Neo4j] Connection failed: {e}")

    def close(self):
        if self.sql:
            self.sql.close()
        if self.neo4j:
            self.neo4j.close()

    # ── ───────────────────────────────────────────────────────────────────────
    # BATCH SYNC  —  SQL Server -> Neo4j
    # ── ───────────────────────────────────────────────────────────────────────

    def batch_sync_to_neo4j(self):
        """
        Reads Customer, Address, and Order data from SQL Server and MERGEs
        the corresponding nodes and relationships into Neo4j.

        Node types created:
          Customer, Device, BankAccount, Phone, Address, Location

        Relationships created:
          USES_DEVICE, HAS_BANK, HAS_PHONE, SHIPS_TO, USED_IN

        Safe to re-run — MERGE is idempotent.
        Call this before any detection scenario.
        """
        cursor = self.sql.cursor()
        print("\n[Sync] Starting batch sync SQL Server -> Neo4j...")

        with self.neo4j.session() as session:

            # ── Constraints (run once, idempotent) ────────────────────────────
            session.run("CREATE CONSTRAINT customer_id IF NOT EXISTS "
                        "FOR (c:Customer) REQUIRE c.customerID IS UNIQUE")
            session.run("CREATE CONSTRAINT device_fp IF NOT EXISTS "
                        "FOR (d:Device) REQUIRE d.fingerprint IS UNIQUE")
            session.run("CREATE CONSTRAINT bank_ref IF NOT EXISTS "
                        "FOR (b:BankAccount) REQUIRE b.bankRef IS UNIQUE")
            session.run("CREATE CONSTRAINT phone_num IF NOT EXISTS "
                        "FOR (p:Phone) REQUIRE p.phoneNumber IS UNIQUE")
            session.run("CREATE CONSTRAINT fraud_ring_id IF NOT EXISTS "
                        "FOR (fr:FraudRing) REQUIRE fr.ringID IS UNIQUE")

            # ── 1. Customer -> Device (USES_DEVICE) ───────────────────────────
            cursor.execute("""
                SELECT CustomerID,
                       FirstName + ' ' + LastName AS FullName,
                       Email, DeviceFingerprint, IPAddress, Postcode,
                       AccountCreatedAt
                FROM Customer
            """)
            rows = cursor.fetchall()
            for r in rows:
                session.run("""
                    MERGE (c:Customer {customerID: $id})
                    SET c.name      = $name,
                        c.email     = $email,
                        c.ipAddress = $ip,
                        c.postcode  = $postcode,
                        c.createdAt = $created
                    MERGE (d:Device {fingerprint: $fp})
                    MERGE (c)-[:USES_DEVICE]->(d)
                """, id=r.CustomerID, name=r.FullName, email=r.Email,
                     fp=r.DeviceFingerprint, ip=r.IPAddress or '',
                     postcode=r.Postcode or '', created=str(r.AccountCreatedAt))
            print(f"[Sync]   Customer -> Device links: {len(rows)}")

            # ── 2. Customer -> BankAccount (HAS_BANK) ─────────────────────────
            # Each distinct BankRef a customer has used becomes an edge.
            cursor.execute("""
                SELECT DISTINCT CustomerID, BankRef
                FROM [Order]
            """)
            rows = cursor.fetchall()
            for r in rows:
                session.run("""
                    MATCH (c:Customer {customerID: $id})
                    MERGE (b:BankAccount {bankRef: $ref})
                    MERGE (c)-[:HAS_BANK]->(b)
                """, id=r.CustomerID, ref=r.BankRef)
            print(f"[Sync]   Customer -> BankAccount links: {len(rows)}")

            # ── 3. Customer -> Phone (HAS_PHONE) ──────────────────────────────
            cursor.execute("SELECT CustomerID, Phone FROM Customer")
            rows = cursor.fetchall()
            for r in rows:
                session.run("""
                    MATCH (c:Customer {customerID: $id})
                    MERGE (p:Phone {phoneNumber: $phone})
                    MERGE (c)-[:HAS_PHONE]->(p)
                """, id=r.CustomerID, phone=r.Phone)
            print(f"[Sync]   Customer -> Phone links: {len(rows)}")

            # ── 4. Customer -> Address (SHIPS_TO) ─────────────────────────────
            cursor.execute("""
                SELECT CustomerID, Postcode, City
                FROM Address
                WHERE AddressType = 'SHIPPING'
            """)
            rows = cursor.fetchall()
            for r in rows:
                session.run("""
                    MATCH (c:Customer {customerID: $id})
                    MERGE (a:Address {postcode: $postcode, city: $city})
                    MERGE (c)-[:SHIPS_TO]->(a)
                """, id=r.CustomerID, postcode=r.Postcode, city=r.City)
            print(f"[Sync]   Customer -> Address links: {len(rows)}")

            # ── 5. BankAccount -> Location (USED_IN) — for Skimming ───────────
            # Each distinct (BankRef, OrderCity) pair creates an edge from the
            # BankAccount node to a Location node. Cards appearing in multiple
            # Location nodes are candidates for skimming detection.
            cursor.execute("""
                SELECT DISTINCT BankRef, OrderCity
                FROM [Order]
            """)
            rows = cursor.fetchall()
            for r in rows:
                session.run("""
                    MERGE (b:BankAccount {bankRef: $ref})
                    MERGE (loc:Location {city: $city})
                    MERGE (b)-[:USED_IN]->(loc)
                """, ref=r.BankRef, city=r.OrderCity)
            print(f"[Sync]   BankAccount -> Location links: {len(rows)}")

        print("[Sync] Batch sync complete.\n")

    # ── ───────────────────────────────────────────────────────────────────────
    # SCENARIO 1  —  register_return()
    # ── ───────────────────────────────────────────────────────────────────────

    def register_return(self, customer_id: int, order_id: int,
                        product_id: int, reason: str,
                        refund_amount: float) -> int:
        """
        Registers a new product return through the full pipeline:

          1. Validates that the order belongs to the customer (SQL).
          2. Inserts a [Return] record with status PENDING (SQL).
          3. Inserts a Refund record with status PENDING (SQL).
          4. Checks Neo4j for suspicious connections on this customer:
               - Shared device fingerprint with other accounts
               - Shared bank account with other accounts
               - Shared phone number with other accounts
               - Duplicate phone number on a separate account
          5. Also runs SQL-side checks:
               - Skimming: same card, different city, within 2 hours
               - Suspect eCommerce: same IP address on multiple accounts
          6. Raises a FraudAlert (SQL) if any check is triggered.

        Returns the new ReturnID, or -1 on validation failure.
        """
        cursor = self.sql.cursor()

        # Validate order belongs to this customer and retrieve payment info
        cursor.execute("""
            SELECT BankRef, CardLastFour, OrderCity
            FROM [Order]
            WHERE OrderID = ? AND CustomerID = ?
        """, order_id, customer_id)
        order = cursor.fetchone()
        if not order:
            print(f"[Return] WARN: Order {order_id} not found for Customer {customer_id}.")
            return -1

        bank_ref = order.BankRef

       # Insert Return
        cursor.execute("""
            INSERT INTO [Return]
                (OrderID, CustomerID, ProductID, ReturnDate,
                ReturnReason, ReturnStatus, RefundAmount)
            VALUES (?, ?, ?, GETDATE(), ?, 'PENDING', ?)
        """, order_id, customer_id, product_id, reason, refund_amount)
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        return_id = int(row[0]) if row and row[0] is not None else None

        # Insert Refund
        cursor.execute("""
            INSERT INTO Refund
                (ReturnID, BankRef, RefundAmount, RefundDate, RefundStatus)
            VALUES (?, ?, ?, GETDATE(), 'PENDING')
        """, return_id, bank_ref, refund_amount)
        self.sql.commit()

        print(f"\n[Return] Return #{return_id} registered — "
              f"Customer {customer_id}, £{refund_amount:.2f}, BankRef {bank_ref}")

        # ── Neo4j checks ──────────────────────────────────────────────────────
        alerts_triggered = []
        with self.neo4j.session() as session:
            neo4j_alerts = self._check_neo4j_connections(customer_id, session)
            alerts_triggered.extend(neo4j_alerts)

        # ── SQL checks ────────────────────────────────────────────────────────
        sql_alerts = self._check_sql_signals(customer_id, cursor)
        alerts_triggered.extend(sql_alerts)

        # ── Raise FraudAlert if any signal fired ──────────────────────────────
        if alerts_triggered:
            score = min(5.0 + len(alerts_triggered) * 1.5, 10.0)
            notes = " | ".join(alerts_triggered)
            alert_type = alerts_triggered[0].split(':')[0].strip()
            # Map verbose label to CHECK-constraint value
            type_map = {
                'SHARED_DEVICE':    'SUSPECT_ECOMMERCE',
                'SHARED_BANK':      'FRAUD_RING',
                'SHARED_PHONE':     'DUPLICATE_PHONE',
                'SKIMMING':         'SKIMMING',
                'SAME_IP':          'SUSPECT_ECOMMERCE',
            }
            db_type = type_map.get(alert_type, 'FRAUD_RING')
            self._raise_fraud_alert(customer_id, db_type, score, notes)
        else:
            print(f"[Return] No suspicious signals detected for Customer {customer_id}.")

        return return_id

    def _check_neo4j_connections(self, customer_id: int, session) -> list:
        """
        Checks Neo4j graph for suspicious connections on a customer.
        Returns a list of alert message strings (empty = no signals).
        """
        alerts = []

        # Shared device fingerprint
        r = session.run("""
            MATCH (c:Customer {customerID: $id})-[:USES_DEVICE]->(d:Device)
                  <-[:USES_DEVICE]-(other:Customer)
            WHERE c <> other
            RETURN count(DISTINCT other) AS cnt,
                   collect(DISTINCT other.customerID)[..3] AS examples,
                   d.fingerprint AS fp
        """, id=customer_id).single()
        if r and r['cnt'] > 0:
            alerts.append(
                f"SHARED_DEVICE: Device {r['fp']} shared with "
                f"{r['cnt']} other account(s): {r['examples']}"
            )

        # Shared bank account
        r = session.run("""
            MATCH (c:Customer {customerID: $id})-[:HAS_BANK]->(b:BankAccount)
                  <-[:HAS_BANK]-(other:Customer)
            WHERE c <> other
            RETURN count(DISTINCT other) AS cnt,
                   collect(DISTINCT other.customerID)[..3] AS examples,
                   b.bankRef AS ref
        """, id=customer_id).single()
        if r and r['cnt'] > 0:
            alerts.append(
                f"SHARED_BANK: BankRef {r['ref']} shared with "
                f"{r['cnt']} other account(s): {r['examples']}"
            )

        # Shared phone number
        r = session.run("""
            MATCH (c:Customer {customerID: $id})-[:HAS_PHONE]->(p:Phone)
                  <-[:HAS_PHONE]-(other:Customer)
            WHERE c <> other
            RETURN count(DISTINCT other) AS cnt,
                   p.phoneNumber AS phone
        """, id=customer_id).single()
        if r and r['cnt'] > 0:
            alerts.append(
                f"SHARED_PHONE: Phone {r['phone']} also registered "
                f"to {r['cnt']} other account(s)"
            )

        return alerts

    def _check_sql_signals(self, customer_id: int, cursor) -> list:
        """
        SQL-side fraud signal checks:
          - Skimming: same BankRef used in two cities within SKIMMING_WINDOW_HOURS
          - Suspect eCommerce: same IP address across multiple accounts
        Returns a list of alert message strings.
        """
        alerts = []

        # Skimming: look for any BankRef this customer has used that appears in
        # two different cities within a short time window on the same day.
        cursor.execute("""
            SELECT o1.BankRef,
                   o1.OrderCity  AS city1, o1.OrderDate AS date1,
                   o2.OrderCity  AS city2, o2.OrderDate AS date2,
                   ABS(DATEDIFF(minute, o1.OrderDate, o2.OrderDate)) AS gap_min
            FROM   [Order] o1
            JOIN   [Order] o2
                ON  o1.BankRef    = o2.BankRef
                AND o1.CustomerID = o2.CustomerID
                AND o1.OrderCity  <> o2.OrderCity
                AND o1.OrderID    < o2.OrderID
                AND ABS(DATEDIFF(minute, o1.OrderDate, o2.OrderDate))
                    <= ?
            WHERE  o1.CustomerID = ?
        """, SKIMMING_WINDOW_HOURS * 60, customer_id)
        row = cursor.fetchone()
        if row:
            alerts.append(
                f"SKIMMING: Card {row.BankRef} used in {row.city1} at "
                f"{row.date1} and {row.city2} at {row.date2} "
                f"({row.gap_min} min gap — impossible travel)"
            )

       # Suspect eCommerce: same IP address on multiple customer accounts
        cursor.execute("""
            SELECT COUNT(*) AS cnt, IPAddress
            FROM   Customer
            WHERE  IPAddress = (SELECT IPAddress FROM Customer WHERE CustomerID = ?)
              AND  IPAddress IS NOT NULL
              AND  IPAddress <> ''
              AND  CustomerID <> ?
            GROUP BY IPAddress
    """, customer_id, customer_id)
        row = cursor.fetchone()
        if row and row.cnt > 0:
            alerts.append(
                f"SAME_IP: IP address {row.IPAddress} shared with "
                f"{row.cnt} other account(s)"
            )
        return alerts

    def _raise_fraud_alert(self, customer_id: int, alert_type: str,
                           score: float, notes: str):
        """
        Inserts a FraudAlert record into SQL Server.
        Skips if an OPEN alert of the same type already exists for this customer.
        """
        cursor = self.sql.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM FraudAlert
            WHERE CustomerID = ? AND AlertType = ? AND Status = 'OPEN'
        """, customer_id, alert_type)
        if cursor.fetchone().cnt > 0:
            print(f"[Alert]  OPEN {alert_type} alert already exists "
                  f"for Customer {customer_id}.")
            return
        cursor.execute("""
            INSERT INTO FraudAlert
                (CustomerID, AnalystID, AlertType, DetectedAt,
                 FraudScore, Status, Notes)
            VALUES (?, NULL, ?, GETDATE(), ?, 'OPEN', ?)
        """, customer_id, alert_type, round(score, 2), notes[:500])
        self.sql.commit()
        print(f"[Alert]  FraudAlert raised — Customer {customer_id}, "
              f"Type: {alert_type}, Score: {score:.1f}")

    # ── ───────────────────────────────────────────────────────────────────────
    # SCENARIO 2  —  detect_fraud_ring()
    # ── ───────────────────────────────────────────────────────────────────────

    def detect_fraud_ring(self):
        """
        Performs a full fraud ring sweep across all customers:

          1. Neo4j: finds clusters of customers sharing BOTH device fingerprint
             AND bank account (strongest signal for an organised ring).
             Also identifies duplicate phone numbers and suspect eCommerce groups.
          2. Filters clusters to RING_MIN_MEMBERS (3+) members.
          3. For each ring:
               a. Queries SQL for total refund exposure (sum of all refunds
                  claimed by ring members).
               b. Creates a FraudRing node in Neo4j.
               c. Adds MEMBER_OF edges from each Customer to the FraudRing.
               d. Adds SHARES_DEVICE_WITH and SHARES_BANK_WITH edges
                  between Customer nodes (for graph traversal / shortest path).
               e. Opens a SQL FraudAlert for each member.
          4. Reports duplicate phone pairs and suspect eCommerce groups.
        """
        cursor = self.sql.cursor()
        print("\n[Detect] Running full fraud ring detection sweep...")

        with self.neo4j.session() as session:

            # ── A. Device + Bank ring detection ───────────────────────────────
            result = session.run("""
                MATCH (c1:Customer)-[:USES_DEVICE]->(d:Device)
                      <-[:USES_DEVICE]-(c2:Customer)
                MATCH (c1)-[:HAS_BANK]->(b:BankAccount)
                      <-[:HAS_BANK]-(c2)
                WHERE c1.customerID < c2.customerID
                  AND NOT (c1)-[:MEMBER_OF]->(:FraudRing)
                RETURN d.fingerprint AS fp,
                       b.bankRef     AS bref,
                       c1.customerID AS id1,
                       c2.customerID AS id2
            """)

            # Cluster by (device, bankRef) key
            clusters = defaultdict(set)
            for r in result:
                key = (r['fp'], r['bref'])
                clusters[key].add(r['id1'])
                clusters[key].add(r['id2'])

            rings = {k: list(v) for k, v in clusters.items()
                     if len(v) >= RING_MIN_MEMBERS}

            rings_created = 0
            for (fp, bref), members in rings.items():
                ring_id = f"RING-{fp.upper()[:20]}"

                # Financial exposure from SQL
                placeholders = ','.join(['?'] * len(members))
                cursor.execute(f"""
                    SELECT ISNULL(SUM(r.RefundAmount), 0) AS exposure
                    FROM   Refund r
                    JOIN   [Return] ret ON r.ReturnID = ret.ReturnID
                    WHERE  ret.CustomerID IN ({placeholders})
                      AND  r.RefundStatus = 'PROCESSED'
                """, *members)
                exposure = float(cursor.fetchone().exposure)

                # Create FraudRing node + MEMBER_OF edges in Neo4j
                session.run("""
                    MERGE (fr:FraudRing {ringID: $ring_id})
                    SET fr.detectedAt    = $detected,
                        fr.memberCount   = $count,
                        fr.sharedDevice  = $fp,
                        fr.sharedBank    = $bref,
                        fr.totalExposure = $exposure
                    WITH fr
                    UNWIND $members AS mid
                    MATCH (c:Customer {customerID: mid})
                    MERGE (c)-[:MEMBER_OF {addedAt: $detected}]->(fr)
                """, ring_id=ring_id, detected=str(datetime.now()),
                     count=len(members), fp=fp, bref=bref,
                     exposure=exposure, members=members)

                # Direct SHARES_* edges between Customer nodes
                for i, id1 in enumerate(members):
                    for id2 in members[i + 1:]:
                        session.run("""
                            MATCH (c1:Customer {customerID: $id1}),
                                  (c2:Customer {customerID: $id2})
                            MERGE (c1)-[:SHARES_DEVICE_WITH]->(c2)
                            MERGE (c2)-[:SHARES_DEVICE_WITH]->(c1)
                            MERGE (c1)-[:SHARES_BANK_WITH]->(c2)
                            MERGE (c2)-[:SHARES_BANK_WITH]->(c1)
                        """, id1=id1, id2=id2)

                # Open SQL FraudAlerts for each member
                for mid in members:
                    self._raise_fraud_alert(
                        mid, 'FRAUD_RING', 9.5,
                        f"Member of {ring_id}. Shared device: {fp}. "
                        f"Shared bank: {bref}. "
                        f"Ring exposure: £{exposure:,.2f}. "
                        f"Ring members: {sorted(members)}."
                    )

                print(f"\n[Ring]   {ring_id}")
                print(f"         Members  : {sorted(members)}")
                print(f"         Device   : {fp}")
                print(f"         Bank Ref : {bref}")
                print(f"         Exposure : £{exposure:,.2f}")
                rings_created += 1

            # ── B. Duplicate Phone detection ───────────────────────────────────
            print("\n[Detect] Checking for duplicate phone numbers...")
            dup_result = session.run("""
                MATCH (c1:Customer)-[:HAS_PHONE]->(p:Phone)
                      <-[:HAS_PHONE]-(c2:Customer)
                WHERE c1.customerID < c2.customerID
                RETURN p.phoneNumber  AS phone,
                       c1.customerID  AS id1, c1.name AS name1,
                       c2.customerID  AS id2, c2.name AS name2
            """)
            dup_count = 0
            for r in dup_result:
                print(f"[DupPhone] {r['phone']} — "
                      f"Customer #{r['id1']} ({r['name1']}) "
                      f"and Customer #{r['id2']} ({r['name2']})")
                # Add SHARES_PHONE_WITH edges
                session.run("""
                    MATCH (c1:Customer {customerID: $id1}),
                          (c2:Customer {customerID: $id2})
                    MERGE (c1)-[:SHARES_PHONE_WITH]->(c2)
                    MERGE (c2)-[:SHARES_PHONE_WITH]->(c1)
                """, id1=r['id1'], id2=r['id2'])
                self._raise_fraud_alert(
                    r['id1'], 'DUPLICATE_PHONE', 5.0,
                    f"Phone {r['phone']} also registered to Customer #{r['id2']} ({r['name2']})."
                )
                self._raise_fraud_alert(
                    r['id2'], 'DUPLICATE_PHONE', 5.0,
                    f"Phone {r['phone']} also registered to Customer #{r['id1']} ({r['name1']})."
                )
                dup_count += 1
            if dup_count == 0:
                print("[DupPhone] No duplicate phone numbers found.")

            # ── C. Suspect eCommerce detection ────────────────────────────────
            print("\n[Detect] Checking for suspect eCommerce clusters...")
            ecom_result = session.run("""
                MATCH (c1:Customer)-[:USES_DEVICE]->(d:Device)
                      <-[:USES_DEVICE]-(c2:Customer)
                WHERE c1.customerID < c2.customerID
                  AND c1.ipAddress = c2.ipAddress
                  AND c1.ipAddress <> ''
                RETURN d.fingerprint       AS fp,
                       c1.ipAddress        AS ip,
                       collect(DISTINCT c1.customerID) + collect(DISTINCT c2.customerID) AS ids
            """)
            ecom_count = 0
            seen_fps = set()
            for r in ecom_result:
                if r['fp'] in seen_fps:
                    continue
                seen_fps.add(r['fp'])
                member_ids = list(set(r['ids']))
                print(f"[eCommerce] Device {r['fp']}, IP {r['ip']} — "
                      f"Customers {sorted(member_ids)}")
                for mid in member_ids:
                    self._raise_fraud_alert(
                        mid, 'SUSPECT_ECOMMERCE', 6.5,
                        f"Device {r['fp']} and IP {r['ip']} shared across "
                        f"Customer IDs {sorted(member_ids)}."
                    )
                # SHARES_ADDRESS_WITH edges (same IP => suspected same operator)
                for i, id1 in enumerate(member_ids):
                    for id2 in member_ids[i + 1:]:
                        session.run("""
                            MATCH (c1:Customer {customerID: $id1}),
                                  (c2:Customer {customerID: $id2})
                            MERGE (c1)-[:SHARES_DEVICE_WITH]->(c2)
                            MERGE (c2)-[:SHARES_DEVICE_WITH]->(c1)
                        """, id1=id1, id2=id2)
                ecom_count += 1
            if ecom_count == 0:
                print("[eCommerce] No suspect eCommerce clusters found.")

            # ── D. Skimming detection (SQL-side, reported here) ───────────────
            print("\n[Detect] Checking for skimming incidents...")
            cursor.execute(f"""
                SELECT o1.CustomerID,
                       o1.BankRef,
                       o1.OrderCity  AS city1, o1.OrderDate AS date1,
                       o2.OrderCity  AS city2, o2.OrderDate AS date2,
                       ABS(DATEDIFF(minute, o1.OrderDate, o2.OrderDate)) AS gap_min
                FROM   [Order] o1
                JOIN   [Order] o2
                    ON  o1.BankRef   = o2.BankRef
                    AND o1.OrderCity <> o2.OrderCity
                    AND o1.OrderID   < o2.OrderID
                    AND ABS(DATEDIFF(minute, o1.OrderDate, o2.OrderDate))
                        <= {SKIMMING_WINDOW_HOURS * 60}
                ORDER  BY gap_min
            """)
            skim_rows = cursor.fetchall()
            if skim_rows:
                for row in skim_rows:
                    print(f"[Skimming] Customer #{row.CustomerID} — "
                          f"Card {row.BankRef}: {row.city1} at {row.date1} "
                          f"and {row.city2} at {row.date2} "
                          f"({row.gap_min} min gap)")
                    self._raise_fraud_alert(
                        row.CustomerID, 'SKIMMING', 8.0,
                        f"Card {row.BankRef} used in {row.city1} at {row.date1} "
                        f"and {row.city2} at {row.date2} — "
                        f"{row.gap_min} minute gap, impossible travel distance."
                    )
            else:
                print("[Skimming] No skimming incidents detected.")

        print(f"\n[Detect] Sweep complete — {rings_created} ring(s) identified.\n")

    # ── ───────────────────────────────────────────────────────────────────────
    # SCENARIO 3  —  investigate_customer()
    # ── ───────────────────────────────────────────────────────────────────────

    def investigate_customer(self, customer_id: int,
                             suspect_id: int = None) -> dict:
        """
        Generates a full investigation report for a flagged customer:

          1. SQL: customer profile, transaction history (orders, returns, refunds),
             active FraudAlerts, and financial exposure summary.
          2. Neo4j: ring membership, all shared-attribute connections
             (device, bank, phone, address), and relationship map.
          3. If suspect_id is provided: runs a shortest-path Cypher query to
             find the shortest chain of connections between the two customers,
             even across indirect shared nodes (useful for uncovering links
             between ring members using different devices).

        Returns a summary dict.
        """
        cursor = self.sql.cursor()
        bar = "=" * 68

        # ── 1. Customer profile ───────────────────────────────────────────────
        cursor.execute("""
            SELECT
                c.CustomerID,
                c.FirstName + ' ' + c.LastName           AS FullName,
                c.Email, c.Phone,
                c.DeviceFingerprint, c.IPAddress, c.Postcode,
                c.AccountCreatedAt,
                DATEDIFF(day, c.AccountCreatedAt, GETDATE()) AS AccountAgeDays,
                COUNT(DISTINCT o.OrderID)                 AS TotalOrders,
                COUNT(DISTINCT ret.ReturnID)              AS TotalReturns,
                CAST(COUNT(DISTINCT ret.ReturnID) AS FLOAT)
                    / NULLIF(COUNT(DISTINCT o.OrderID), 0) AS ReturnRate,
                ISNULL(SUM(r.RefundAmount), 0)            AS TotalRefunded,
                MAX(ret.ReturnDate)                       AS LastReturnDate
            FROM Customer c
            LEFT JOIN [Order]  o   ON c.CustomerID = o.CustomerID
            LEFT JOIN [Return] ret ON o.OrderID    = ret.OrderID
            LEFT JOIN Refund   r   ON ret.ReturnID = r.ReturnID
            WHERE c.CustomerID = ?
            GROUP BY c.CustomerID, c.FirstName, c.LastName, c.Email,
                     c.Phone, c.DeviceFingerprint, c.IPAddress,
                     c.Postcode, c.AccountCreatedAt
        """, customer_id)
        profile = cursor.fetchone()

        if not profile:
            print(f"[Inv] Customer {customer_id} not found.")
            return {}

        # ── 2. Active FraudAlerts ─────────────────────────────────────────────
        cursor.execute("""
            SELECT fa.AlertType, fa.DetectedAt, fa.FraudScore,
                   fa.Status, fa.Notes,
                   a.FirstName + ' ' + a.LastName AS Analyst
            FROM   FraudAlert fa
            LEFT JOIN Analyst a ON fa.AnalystID = a.AnalystID
            WHERE  fa.CustomerID = ?
            ORDER  BY fa.DetectedAt DESC
        """, customer_id)
        alerts = cursor.fetchall()

        # ── 3. Order / Return / Refund history ───────────────────────────────
        cursor.execute("""
            SELECT
                o.OrderID, o.OrderDate, o.TotalAmount,
                o.BankRef, o.OrderCity, o.OrderStatus,
                p.ProductName, p.Category,
                ret.ReturnID, ret.ReturnStatus, ret.ReturnDate,
                r.RefundAmount, r.RefundStatus
            FROM      [Order]  o
            LEFT JOIN [Return] ret ON o.OrderID    = ret.OrderID
            LEFT JOIN Product  p   ON ret.ProductID = p.ProductID
            LEFT JOIN Refund   r   ON ret.ReturnID  = r.ReturnID
            WHERE o.CustomerID = ?
            ORDER BY o.OrderDate DESC
        """, customer_id)
        orders = cursor.fetchall()

        # ── 4. Neo4j: Ring membership + connections ───────────────────────────
        with self.neo4j.session() as session:

            ring = session.run("""
                MATCH (c:Customer {customerID: $id})-[:MEMBER_OF]->(fr:FraudRing)
                RETURN fr.ringID        AS ring_id,
                       fr.memberCount   AS count,
                       fr.sharedDevice  AS device,
                       fr.sharedBank    AS bank,
                       fr.totalExposure AS exposure
            """, id=customer_id).single()

            connections = session.run("""
                MATCH (c:Customer {customerID: $id})
                OPTIONAL MATCH (c)-[:USES_DEVICE]->(d:Device)
                               <-[:USES_DEVICE]-(c2:Customer)
                WHERE c2 <> c
                OPTIONAL MATCH (c)-[:HAS_BANK]->(b:BankAccount)
                               <-[:HAS_BANK]-(c3:Customer)
                WHERE c3 <> c
                OPTIONAL MATCH (c)-[:HAS_PHONE]->(p:Phone)
                               <-[:HAS_PHONE]-(c4:Customer)
                WHERE c4 <> c
                RETURN
                    collect(DISTINCT c2.customerID) AS shared_device_with,
                    collect(DISTINCT c3.customerID) AS shared_bank_with,
                    collect(DISTINCT c4.customerID) AS shared_phone_with
            """, id=customer_id).single()

            # ── 5. Shortest path to suspect (optional) ────────────────────────
            path_info = None
            if suspect_id:
                path_result = session.run("""
                    MATCH path = shortestPath(
                        (c1:Customer {customerID: $id1})
                        -[*..10]-
                        (c2:Customer {customerID: $id2})
                    )
                    RETURN
                        [n IN nodes(path) |
                            CASE
                                WHEN n:Customer    THEN 'Customer#' + toString(n.customerID)
                                WHEN n:Device      THEN 'Device:'   + n.fingerprint
                                WHEN n:BankAccount THEN 'Bank:'     + n.bankRef
                                WHEN n:Phone       THEN 'Phone:'    + n.phoneNumber
                                WHEN n:Address     THEN 'Address:'  + n.postcode
                                WHEN n:Location    THEN 'Location:' + n.city
                                WHEN n:FraudRing   THEN 'Ring:'     + n.ringID
                                ELSE 'Node'
                            END
                        ] AS path_nodes,
                        length(path) AS hops
                """, id1=customer_id, id2=suspect_id).single()
                if path_result:
                    path_info = (path_result['path_nodes'], path_result['hops'])

        # ── Print report ──────────────────────────────────────────────────────
        print(f"\n{bar}")
        print(f"  CUSTOMER INVESTIGATION REPORT")
        print(bar)
        print(f"  Customer       : #{profile.CustomerID} — {profile.FullName}")
        print(f"  Email          : {profile.Email}")
        print(f"  Phone          : {profile.Phone}")
        print(f"  Device         : {profile.DeviceFingerprint}")
        print(f"  IP Address     : {profile.IPAddress}")
        print(f"  Postcode       : {profile.Postcode}")
        print(f"  Account Age    : {profile.AccountAgeDays} days "
              f"(created {profile.AccountCreatedAt})")
        rate_str = f"{profile.ReturnRate:.0%}" if profile.ReturnRate else "N/A"
        print(f"  Orders/Returns : {profile.TotalOrders} / {profile.TotalReturns}"
              f"  ({rate_str} return rate)")
        print(f"  Total Refunded : £{profile.TotalRefunded:,.2f}")
        if profile.LastReturnDate:
            print(f"  Last Return    : {profile.LastReturnDate}")

        print(f"\n  FRAUD ALERTS ({len(alerts)}):")
        print("-" * 68)
        if alerts:
            for a in alerts:
                analyst = a.Analyst or "System"
                print(f"  [{a.Status:<10}] {a.AlertType:<22} "
                      f"Score:{a.FraudScore:>5.1f}  Analyst: {analyst}")
                print(f"    {a.DetectedAt}")
                print(f"    {a.Notes}")
                print()
        else:
            print("  No active fraud alerts.")

        if ring:
            print(f"\n  RING MEMBERSHIP (Neo4j):")
            print("-" * 68)
            print(f"  Ring ID        : {ring['ring_id']}")
            print(f"  Member Count   : {ring['count']}")
            print(f"  Shared Device  : {ring['device']}")
            print(f"  Shared Bank    : {ring['bank']}")
            print(f"  Ring Exposure  : £{ring['exposure']:,.2f}")

        if connections:
            print(f"\n  SHARED ATTRIBUTES (Neo4j):")
            print("-" * 68)
            if connections['shared_device_with']:
                print(f"  Device shared with    : "
                      f"Customer(s) {connections['shared_device_with']}")
            if connections['shared_bank_with']:
                print(f"  Bank shared with      : "
                      f"Customer(s) {connections['shared_bank_with']}")
            if connections['shared_phone_with']:
                print(f"  Phone shared with     : "
                      f"Customer(s) {connections['shared_phone_with']}")

        print(f"\n  TRANSACTION HISTORY (most recent first):")
        print("-" * 68)
        for o in orders:
            ret_str  = f"Return #{o.ReturnID} [{o.ReturnStatus}]" if o.ReturnID else "No return"
            ref_str  = f"Refund £{o.RefundAmount:.2f} [{o.RefundStatus}]" if o.RefundAmount else ""
            prod_str = f"{o.ProductName} ({o.Category})" if o.ProductName else "—"
            print(f"  Order #{o.OrderID:>3} | {o.OrderDate} | "
                  f"£{o.TotalAmount:>8.2f} | {o.BankRef} | {o.OrderCity}")
            print(f"    Product: {prod_str}")
            print(f"    {ret_str}  {ref_str}")
            print()

        if path_info:
            nodes, hops = path_info
            print(f"\n  SHORTEST PATH to Customer #{suspect_id} ({hops} hop(s)):")
            print("-" * 68)
            print("  " + " -> ".join(nodes))

        print(f"\n{bar}\n")

        return {
            'customer_id':   customer_id,
            'total_refunded': float(profile.TotalRefunded),
            'return_rate':   float(profile.ReturnRate or 0),
            'alerts':        [(a.AlertType, float(a.FraudScore or 0)) for a in alerts],
            'ring':          dict(ring) if ring else None,
            'path_to_suspect': path_info,
        }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    bar = "=" * 68
    print(bar)
    print("  AMAZON RETURN FRAUD RING DETECTION SYSTEM")
    print("  BEMM459 — University of Exeter")
    print("  Polyglot Persistence: SQL Server + Neo4j AuraDB")
    print(bar)

    system = FraudDetectionSystem()

    try:
        # ── Step 1: Populate Neo4j from SQL Server ────────────────────────────
        system.batch_sync_to_neo4j()

        # ── Step 2: Full fraud ring detection sweep ───────────────────────────
        # Detects all four patterns and raises FraudAlerts in SQL.
        system.detect_fraud_ring()

        # ── Step 3: Investigate a known ring member ───────────────────────────
        # Customer #1 (Alice Thompson) is a fraud ring member.
        # Also find the shortest path to Customer #4 (David Evans),
        # who shares the same bank ref but uses a different device,
        # so their connection runs through the BankAccount node.
        system.investigate_customer(customer_id=1, suspect_id=4)

        # ── Step 4: Simulate a live return from a ring member ─────────────────
        # Customer #2 attempts to return an AirPods Pro (Product #2).
        # register_return() will detect the shared device + bank signals
        # and automatically raise a FRAUD_RING alert.
        print(f"\n{bar}")
        print("  SCENARIO 1 — Live return from a ring member (Customer #2)")
        print(bar)
        system.register_return(
            customer_id=2,
            order_id=14,       # C2's first order
            product_id=2,      # Apple AirPods Pro
            reason="Item not as described",
            refund_amount=249.99,
        )

        # ── Step 5: Investigate a skimming victim ────────────────────────────
        # Customer #14 — card used in London and Edinburgh within 45 minutes.
        system.investigate_customer(customer_id=14)

    finally:
        system.close()
        print("\n[Done] All database connections closed.")
