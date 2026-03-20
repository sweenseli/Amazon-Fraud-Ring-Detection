// ============================================================
// Amazon Return Fraud Ring Detection System
// BEMM459 - Database Technologies for Business Analytics
// University of Exeter
// neo4j_setup.cypher
// ============================================================


// VERIFY GRAPH IS POPULATED
// Run this first to confirm seed_data.py has been executed successfully.

// Count all nodes by label
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY label;

// Expected output:
// Address      : 8
// BankAccount  : 5+
// Customer     : 31
// Device       : 10
// FraudRing    : 2
// Location     : 6
// Phone        : 4


// VERIFY CONSTRAINTS AND INDEXES

// Show all constraints (expect 7)
SHOW CONSTRAINTS;

// Show all indexes (expect 15 total - 7 constraint-backed + 6 performance + 2 system)
SHOW INDEXES;


// FRAUD PATTERN 1 - FRAUD RING 
// Finds customers sharing both a device fingerprint AND a bank reference.
// Ring A: CustomerIDs 1-5 share fp_ring_alpha_a1b2 + BARC-9921-GBP
// Ring B: CustomerIDs 6-9 share fp_ring_gamma_c3d4 + BARC-3344-GBP

// Detect all fraud ring pairs
MATCH (c1:Customer)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(c2:Customer)
MATCH (c1)-[:HAS_BANK]->(b:BankAccount)<-[:HAS_BANK]-(c2)
WHERE c1.customerID < c2.customerID
RETURN c1.customerID AS customer_A,
       c2.customerID AS customer_B,
       d.fingerprint AS shared_device,
       b.bankRef     AS shared_bank
ORDER BY customer_A;

// Visual graph - full Ring A traversal from Customer 1
// Switch to GRAPH VIEW in Neo4j Browser to see the ring network.
MATCH path = (c:Customer {customerID: 1})
    -[:SHARES_DEVICE_WITH|SHARES_BANK_WITH|SHARES_ADDRESS_WITH*1..4]-
    (connected:Customer)
RETURN path;

// Visual graph - full Ring B traversal from Customer 6
MATCH path = (c:Customer {customerID: 6})
    -[:SHARES_DEVICE_WITH|SHARES_BANK_WITH|SHARES_ADDRESS_WITH*1..4]-
    (connected:Customer)
RETURN path;

// List all members of Ring A with ring details
MATCH (r:FraudRing {ringID: 'RING-FP_RING_ALPHA_A1B2'})<-[:MEMBER_OF]-(c:Customer)
RETURN r.ringID        AS ring_id,
       count(DISTINCT c) AS members,
       r.totalExposure AS total_exposure_gbp,
       r.sharedDevice  AS device,
       r.sharedBank    AS bank;

// List all members of Ring B
MATCH (r:FraudRing {ringID: 'RING-FP_RING_GAMMA_C3D4'})<-[:MEMBER_OF]-(c:Customer)
RETURN r.ringID          AS ring_id,
       count(DISTINCT c) AS members,
       r.totalExposure   AS total_exposure_gbp,
       r.sharedDevice    AS device,
       r.sharedBank      AS bank;


// FRAUD PATTERN 2 - DUPLICATE PHONE
// Finds customers sharing the same phone number.
// Dup Phone A: CustomerIDs 10 + 11 share 07700900999
// Dup Phone B: CustomerIDs 12 + 13 share 07700901234

// Detect all duplicate phone pairs
MATCH (c1:Customer)-[:HAS_PHONE]->(p:Phone)<-[:HAS_PHONE]-(c2:Customer)
WHERE c1.customerID < c2.customerID
RETURN c1.customerID AS customer_A,
       c2.customerID AS customer_B,
       p.phoneNumber AS shared_phone;

// Visual graph - duplicate phone pair
MATCH path = (c1:Customer {customerID: 10})-[:HAS_PHONE|SHARES_PHONE_WITH*1..2]-(connected)
RETURN path;


// FRAUD PATTERN 3 - CARD SKIMMING
// Finds bank accounts used in multiple geographic locations.
// Customer 14: BARC-7788-GBP used London 09:00 -> Edinburgh 09:45 (45 min gap)
// Customer 15: BARC-5566-GBP used Manchester 10:00 -> Bristol 11:00 (60 min gap)

// Detect all skimming signals
MATCH (b:BankAccount)-[:USED_IN]->(loc:Location)
WITH b, collect(loc.city) AS cities
WHERE size(cities) > 1
RETURN b.bankRef AS bank_ref,
       cities    AS locations_used;

// Visual graph - skimming geography for Customer 14's card
MATCH path = (b:BankAccount {bankRef: 'BARC-7788-GBP'})-[:USED_IN]->(loc:Location)
RETURN path;

// Visual graph - skimming geography for Customer 15's card
MATCH path = (b:BankAccount {bankRef: 'BARC-5566-GBP'})-[:USED_IN]->(loc:Location)
RETURN path;


// FRAUD PATTERN 4 - SUSPECT eCOMMERCE
// Finds multiple customer accounts operating from the same device fingerprint.
// eCommerce A: CustomerIDs 16-18 share fp_shared_ecom_a + IP 85.10.20.30
// eCommerce B: CustomerIDs 19-21 share fp_shared_ecom_b + IP 91.22.33.44

// Detect all suspect eCommerce clusters
MATCH (c:Customer)-[:USES_DEVICE]->(d:Device)
WITH d, collect(DISTINCT c.customerID) AS suspects
WHERE size(suspects) > 1
RETURN d.fingerprint AS shared_device,
       suspects      AS customer_ids
ORDER BY size(suspects) DESC;

// Visual graph - eCommerce A cluster
MATCH path = (c:Customer)-[:USES_DEVICE|SHARES_DEVICE_WITH*1..2]-(connected)
WHERE c.customerID IN [16, 17, 18]
RETURN path;


// SHORTEST PATH - SCENARIO 3
// Finds the shortest connection between any two customers through shared nodes.
// Useful for finding indirect connections invisible in SQL alone.

// Shortest path between Customer 1 (Ring A) and Customer 4 (Ring A)
// These share device + bank so path should be short (2 hops through shared node)
MATCH path = shortestPath(
    (c1:Customer {customerID: 1})-[*..10]-(c2:Customer {customerID: 4})
)
RETURN [n IN nodes(path) |
    CASE
        WHEN n:Customer    THEN 'Customer#'  + toString(n.customerID)
        WHEN n:Device      THEN 'Device:'    + n.fingerprint
        WHEN n:BankAccount THEN 'Bank:'      + n.bankRef
        WHEN n:Phone       THEN 'Phone:'     + n.phoneNumber
        WHEN n:Address     THEN 'Address:'   + n.postcode
        WHEN n:Location    THEN 'Location:'  + n.city
        WHEN n:FraudRing   THEN 'Ring:'      + n.ringID
        ELSE 'Node'
    END
] AS path_nodes,
length(path) AS hops;

// Shortest path between Ring A member (1) and Ring B member (6)
// These are in different rings - path will go through shared nodes if any exist
MATCH path = shortestPath(
    (c1:Customer {customerID: 1})-[*..10]-(c2:Customer {customerID: 6})
)
RETURN [n IN nodes(path) |
    CASE
        WHEN n:Customer    THEN 'Customer#'  + toString(n.customerID)
        WHEN n:Device      THEN 'Device:'    + n.fingerprint
        WHEN n:BankAccount THEN 'Bank:'      + n.bankRef
        WHEN n:Phone       THEN 'Phone:'     + n.phoneNumber
        WHEN n:Address     THEN 'Address:'   + n.postcode
        WHEN n:FraudRing   THEN 'Ring:'      + n.ringID
        ELSE 'Node'
    END
] AS path_nodes,
length(path) AS hops;


// FULL GRAPH VIEW 
// Shows the complete fraud network for all fraud group members and their connections.
// Switch to GRAPH VIEW.

// Full fraud network - all 21 fraud group members and their shared nodes
MATCH path = (c:Customer)-[]->(n)
WHERE c.customerID IN [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]
RETURN path;

// Just the SHARES_ relationships - cleaner ring view
MATCH path = (c1:Customer)-[:SHARES_DEVICE_WITH|SHARES_BANK_WITH|SHARES_ADDRESS_WITH|SHARES_PHONE_WITH]-(c2:Customer)
WHERE c1.customerID IN [1,2,3,4,5,6,7,8,9]
RETURN path;


// SHARED ADDRESS VERIFICATION
// Confirms customers sharing delivery addresses.

// Find all customers sharing the same address
MATCH (c1:Customer)-[:SHIPS_TO]->(a:Address)<-[:SHIPS_TO]-(c2:Customer)
WHERE c1.customerID < c2.customerID
RETURN c1.customerID AS customer_A,
       c2.customerID AS customer_B,
       a.postcode    AS shared_postcode,
       a.city        AS city;


// CLEANUP (only run if resetting)
// WARNING: This deletes ALL data. Only run if you want to reset and re-run seed_data.py.

// MATCH (n) DETACH DELETE n;
