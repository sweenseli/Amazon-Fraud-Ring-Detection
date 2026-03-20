from neo4j import GraphDatabase

URI      = "neo4j+ssc://78fe787f.databases.neo4j.io:7687"
USER     = "78fe787f"
PASSWORD = "xmGh-UUzmmA0b8iHaJiN-H-tONUMsO4Oz5enBA2zSnA"

def seed_database():
    with GraphDatabase.driver(URI, auth=(USER, PASSWORD)) as driver:
        with driver.session() as session:

            # Clear all existing data
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared existing data.")

            # Constraints and indexes
            session.run("CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customerID IS UNIQUE")
            session.run("CREATE CONSTRAINT device_fp IF NOT EXISTS FOR (d:Device) REQUIRE d.fingerprint IS UNIQUE")
            session.run("CREATE CONSTRAINT bank_ref IF NOT EXISTS FOR (b:BankAccount) REQUIRE b.bankRef IS UNIQUE")
            session.run("CREATE CONSTRAINT phone_num IF NOT EXISTS FOR (p:Phone) REQUIRE p.phoneNumber IS UNIQUE")
            session.run("CREATE CONSTRAINT address_key IF NOT EXISTS FOR (a:Address) REQUIRE (a.postcode, a.city) IS UNIQUE")
            session.run("CREATE CONSTRAINT location_city IF NOT EXISTS FOR (l:Location) REQUIRE l.city IS UNIQUE")
            session.run("CREATE CONSTRAINT fraud_ring_id IF NOT EXISTS FOR (f:FraudRing) REQUIRE f.ringID IS UNIQUE")
            session.run("CREATE INDEX customer_postcode IF NOT EXISTS FOR (c:Customer) ON (c.postcode)")
            session.run("CREATE INDEX customer_ip IF NOT EXISTS FOR (c:Customer) ON (c.ipAddress)")
            session.run("CREATE INDEX device_fingerprint IF NOT EXISTS FOR (d:Device) ON (d.fingerprint)")
            session.run("CREATE INDEX bank_ref_idx IF NOT EXISTS FOR (b:BankAccount) ON (b.bankRef)")
            session.run("CREATE INDEX phone_number IF NOT EXISTS FOR (p:Phone) ON (p.phoneNumber)")
            session.run("CREATE INDEX location_city_idx IF NOT EXISTS FOR (l:Location) ON (l.city)")
            print("Constraints and indexes created.")

            # Device nodes
            session.run("""
            MERGE (d1:Device {fingerprint: 'fp_ring_alpha_a1b2'})
            MERGE (d2:Device {fingerprint: 'fp_ring_gamma_c3d4'})
            MERGE (d3:Device {fingerprint: 'fp_shared_ecom_a'})
            MERGE (d4:Device {fingerprint: 'fp_shared_ecom_b'})
            MERGE (d5:Device {fingerprint: 'fp_7929de_d4e7'})
            MERGE (d6:Device {fingerprint: 'fp_144251_6e4c'})
            MERGE (d7:Device {fingerprint: 'fp_aa36d1_3722'})
            MERGE (d8:Device {fingerprint: 'fp_597de1_23a4'})
            MERGE (d9:Device {fingerprint: 'fp_ac6d52_2e6a'})
            MERGE (d10:Device {fingerprint: 'fp_c41c50_d514'})
            """)
            print("Devices created.")

            # BankAccount nodes
            session.run("""
            MERGE (b1:BankAccount {bankRef: 'BARC-9921-GBP'})
            MERGE (b2:BankAccount {bankRef: 'BARC-3344-GBP'})
            MERGE (b3:BankAccount {bankRef: 'BARC-7788-GBP'})
            MERGE (b4:BankAccount {bankRef: 'BARC-5566-GBP'})
            MERGE (b5:BankAccount {bankRef: 'BARC-5304-GBP'})
            MERGE (b6:BankAccount {bankRef: 'BARC-9742-GBP'})
            """)
            print("Bank accounts created.")

            # Phone nodes
            session.run("""
            MERGE (p1:Phone {phoneNumber: '07700900999'})
            MERGE (p2:Phone {phoneNumber: '07700901234'})
            """)
            print("Phone nodes created.")

            # Address nodes
            session.run("""
            MERGE (a1:Address {postcode: 'EC1A 1BB', city: 'London'})
            MERGE (a2:Address {postcode: 'E1 6RF',   city: 'London'})
            MERGE (a3:Address {postcode: 'BD1 1AA',  city: 'Bradford'})
            MERGE (a4:Address {postcode: 'LE1 1AA',  city: 'Leicester'})
            MERGE (a5:Address {postcode: 'BS1 1AA',  city: 'Bristol'})
            MERGE (a6:Address {postcode: 'CV1 1AA',  city: 'Coventry'})
            MERGE (a7:Address {postcode: 'NG1 1AA',  city: 'Nottingham'})
            MERGE (a8:Address {postcode: 'G1 1AF',   city: 'Glasgow'})
            """)
            print("Addresses created.")

            # Location nodes (for skimming signal)
            session.run("""
            MERGE (l1:Location {city: 'London'})
            MERGE (l2:Location {city: 'Edinburgh'})
            MERGE (l3:Location {city: 'Manchester'})
            MERGE (l4:Location {city: 'Bristol'})
            MERGE (l5:Location {city: 'Leeds'})
            MERGE (l6:Location {city: 'Glasgow'})
            """)
            print("Location nodes created.")

            # Customer nodes - fraud groups + sample legitimate

            # Ring A - IDs 1-5
            ring_a = [
                (1,  'Ethan',    'Williams', 'ethan.williams1@icloud.com',     '07700900101', 'fp_ring_alpha_a1b2', '192.168.10.1', 'EC1A 1BB'),
                (2,  'Dylan',    'Thompson', 'dylan.thompson2@yahoo.co.uk',    '07700900102', 'fp_ring_alpha_a1b2', '192.168.10.2', 'EC1A 1BB'),
                (3,  'Michael',  'Campbell', 'michael.campbell3@outlook.com',  '07700900103', 'fp_ring_alpha_a1b2', '192.168.10.3', 'EC1A 1BB'),
                (4,  'Benjamin', 'Edwards',  'benjamin.edwards4@icloud.com',   '07700900104', 'fp_ring_alpha_a1b2', '192.168.10.4', 'EC1A 1BB'),
                (5,  'Jack',     'Cooper',   'jack.cooper5@outlook.com',       '07700900105', 'fp_ring_alpha_a1b2', '192.168.10.5', 'EC1A 1BB'),
            ]

            # Ring B - IDs 6-9
            ring_b = [
                (6,  'Priya',    'Campbell', 'priya.campbell6@gmail.com',      '07700900200', 'fp_ring_gamma_c3d4', '192.168.20.1', 'E1 6RF'),
                (7,  'Grace',    'King',     'grace.king7@yahoo.co.uk',        '07700900201', 'fp_ring_gamma_c3d4', '192.168.20.2', 'E1 6RF'),
                (8,  'Isabella', 'Hall',     'isabella.hall8@gmail.com',       '07700900202', 'fp_ring_gamma_c3d4', '192.168.20.3', 'E1 6RF'),
                (9,  'William',  'Ward',     'william.ward9@icloud.com',       '07700900203', 'fp_ring_gamma_c3d4', '192.168.20.4', 'E1 6RF'),
            ]

            # Duplicate Phone A - IDs 10-11 (share 07700900999)
            dup_phone_a = [
                (10, 'James',   'Ali',   'james.ali10@yahoo.co.uk',   '07700900999', 'fp_aa36d1_3722', '210.82.60.78',   'G1 1AF'),
                (11, 'Ethan',   'Evans', 'ethan.evans11@icloud.com',  '07700900999', 'fp_597de1_23a4', '225.36.252.170', 'B1 1BB'),
            ]

            # Duplicate Phone B - IDs 12-13 (share 07700901234)
            dup_phone_b = [
                (12, 'Isabella', 'Clarke', 'isabella.clarke12@icloud.com', '07700901234', 'fp_ac6d52_2e6a', '134.56.105.77', 'OX1 2JD'),
                (13, 'Ethan',    'Scott',  'ethan.scott13@yahoo.co.uk',    '07700901234', 'fp_c41c50_d514', '71.15.142.243', 'EH1 1BB'),
            ]

            # Skimming - IDs 14-15
            skimming = [
                (14, 'Amy',   'Martin', 'amy.martin14@icloud.com',   '07700900314', 'fp_7929de_d4e7', '152.225.188.234', 'BD1 1AA'),
                (15, 'Priya', 'White',  'priya.white15@icloud.com',  '07700900315', 'fp_144251_6e4c', '45.160.173.110',  'LE1 1AA'),
            ]

            # eCommerce A - IDs 16-18 (share device + IP)
            ecom_a = [
                (16, 'Priya',  'Clarke',    'priya.clarke16@outlook.com',   '07700900416', 'fp_shared_ecom_a', '85.10.20.30', 'BS1 1AA'),
                (17, 'Sarah',  'Mitchell',  'sarah.mitchell17@gmail.com',   '07700900417', 'fp_shared_ecom_a', '85.10.20.30', 'CV1 1AA'),
                (18, 'Laura',  'Thompson',  'laura.thompson18@gmail.com',   '07700900418', 'fp_shared_ecom_a', '85.10.20.30', 'NG1 1AA'),
            ]

            # eCommerce B - IDs 19-21 (share device + IP)
            ecom_b = [
                (19, 'Isla',   'Price',  'isla.price19@icloud.com',      '07700900519', 'fp_shared_ecom_b', '91.22.33.44', 'CV1 1AA'),
                (20, 'Daniel', 'Carter', 'daniel.carter20@yahoo.co.uk',  '07700900520', 'fp_shared_ecom_b', '91.22.33.44', 'WC2N 5DU'),
                (21, 'Emma',   'Smith',  'emma.smith21@yahoo.co.uk',     '07700900521', 'fp_shared_ecom_b', '91.22.33.44', 'N1 9GU'),
            ]

            # Sample legitimate customers - IDs 22-31
            legitimate = [
                (22, 'Kevin',   'King',      'kevin.king22@outlook.com',      '07711830043', 'fp_be5ec3_fc95', '143.126.12.249', 'BD1 1AA'),
                (23, 'Ava',     'Singh',     'ava.singh23@yahoo.co.uk',       '07781742470', 'fp_9f1584_706e', '89.241.164.172', 'N1 9GU'),
                (24, 'Kevin',   'Hussain',   'kevin.hussain24@outlook.com',   '07788070348', 'fp_357f75_5a5b', '98.201.134.82',  'SO14 0YG'),
                (25, 'Sophie',  'King',      'sophie.king25@yahoo.co.uk',     '07723524492', 'fp_34c778_6005', '179.106.104.39', 'WC2N 5DU'),
                (26, 'Callum',  'Smith',     'callum.smith26@outlook.com',    '07788165507', 'fp_5c636e_a165', '77.96.47.194',   'G1 1AF'),
                (27, 'Amelia',  'Williams',  'amelia.williams27@hotmail.co.uk','07768524572', 'fp_e0a643_35cf', '138.121.61.218', 'SO14 0YG'),
                (28, 'Daniel',  'Johnson',   'daniel.johnson28@gmail.com',    '07748283485', 'fp_6da8d6_97e5', '58.76.219.182',  'WC2N 5DU'),
                (29, 'Emily',   'Davies',    'emily.davies29@yahoo.co.uk',    '07753611082', 'fp_ad9b62_787a', '37.206.118.235', 'EH1 1BB'),
                (30, 'Logan',   'Young',     'logan.young30@gmail.com',       '07769490249', 'fp_c379cb_5d5c', '15.143.105.248', 'G1 1AF'),
                (31, 'Steven',  'Davies',    'steven.davies31@icloud.com',    '07738184109', 'fp_abe717_fdd8', '107.142.135.35', 'OX1 2JD'),
            ]

            all_customers = ring_a + ring_b + dup_phone_a + dup_phone_b + skimming + ecom_a + ecom_b + legitimate

            for cid, fname, lname, email, phone, fp, ip, postcode in all_customers:
                session.run("""
                    MERGE (c:Customer {customerID: $id})
                    SET c.name      = $name,
                        c.email     = $email,
                        c.phone     = $phone,
                        c.ipAddress = $ip,
                        c.postcode  = $postcode
                """, id=cid, name=f"{fname} {lname}", email=email,
                     phone=phone, ip=ip, postcode=postcode)
            print(f"Customers created ({len(all_customers)} total).")

            # Base relationships - USES_DEVICE, HAS_BANK, SHIPS_TO

            # Ring A base links
            for cid, _, _, _, _, fp, _, postcode in ring_a:
                session.run("""
                    MATCH (c:Customer {customerID: $id}),
                          (d:Device {fingerprint: $fp}),
                          (b:BankAccount {bankRef: 'BARC-9921-GBP'}),
                          (a:Address {postcode: $postcode})
                    MERGE (c)-[:USES_DEVICE]->(d)
                    MERGE (c)-[:HAS_BANK]->(b)
                    MERGE (c)-[:SHIPS_TO]->(a)
                """, id=cid, fp=fp, postcode=postcode)

            # Ring B base links
            for cid, _, _, _, _, fp, _, postcode in ring_b:
                session.run("""
                    MATCH (c:Customer {customerID: $id}),
                          (d:Device {fingerprint: $fp}),
                          (b:BankAccount {bankRef: 'BARC-3344-GBP'}),
                          (a:Address {postcode: $postcode})
                    MERGE (c)-[:USES_DEVICE]->(d)
                    MERGE (c)-[:HAS_BANK]->(b)
                    MERGE (c)-[:SHIPS_TO]->(a)
                """, id=cid, fp=fp, postcode=postcode)

            # All other customers - device and address links
            for cid, _, _, _, _, fp, _, postcode in (dup_phone_a + dup_phone_b + skimming + ecom_a + ecom_b + legitimate):
                session.run("""
                    MATCH (c:Customer {customerID: $id}),
                          (d:Device {fingerprint: $fp})
                    MERGE (c)-[:USES_DEVICE]->(d)
                """, id=cid, fp=fp)
                # Link to address if it exists
                session.run("""
                    MATCH (c:Customer {customerID: $id})
                    MERGE (a:Address {postcode: $postcode, city: $postcode})
                    MERGE (c)-[:SHIPS_TO]->(a)
                """, id=cid, postcode=postcode)

            print("Base relationships (USES_DEVICE, HAS_BANK, SHIPS_TO) created.")

            # HAS_PHONE relationships
            phone_links = [
                (10, '07700900999'),
                (11, '07700900999'),
                (12, '07700901234'),
                (13, '07700901234'),
            ]
            for cid, phone in phone_links:
                session.run("""
                    MATCH (c:Customer {customerID: $id}),
                          (p:Phone {phoneNumber: $phone})
                    MERGE (c)-[:HAS_PHONE]->(p)
                """, id=cid, phone=phone)
            print("HAS_PHONE relationships created.")

            # USED_IN relationships - skimming signal
            # Customer 14: BARC-7788-GBP used London 09:00 -> Edinburgh 09:45 (45 min gap)
            session.run("""
                MATCH (b:BankAccount {bankRef: 'BARC-7788-GBP'})
                MERGE (l1:Location {city: 'London'})
                MERGE (l2:Location {city: 'Edinburgh'})
                MERGE (b)-[:USED_IN]->(l1)
                MERGE (b)-[:USED_IN]->(l2)
            """)
            # Customer 15: BARC-5566-GBP used Manchester 10:00 -> Bristol 11:00 (60 min gap)
            session.run("""
                MATCH (b:BankAccount {bankRef: 'BARC-5566-GBP'})
                MERGE (l3:Location {city: 'Manchester'})
                MERGE (l4:Location {city: 'Bristol'})
                MERGE (b)-[:USED_IN]->(l3)
                MERGE (b)-[:USED_IN]->(l4)
            """)
            print("USED_IN relationships created (skimming signals).")

            # SHARES_ relationships

            # Ring A - all pairs
            ring_a_ids = [1, 2, 3, 4, 5]
            for i, id1 in enumerate(ring_a_ids):
                for id2 in ring_a_ids[i+1:]:
                    session.run("""
                        MATCH (c1:Customer {customerID: $id1}),
                              (c2:Customer {customerID: $id2})
                        MERGE (c1)-[:SHARES_DEVICE_WITH]->(c2)
                        MERGE (c1)-[:SHARES_BANK_WITH]->(c2)
                        MERGE (c1)-[:SHARES_ADDRESS_WITH]->(c2)
                    """, id1=id1, id2=id2)

            # Ring B - all pairs
            ring_b_ids = [6, 7, 8, 9]
            for i, id1 in enumerate(ring_b_ids):
                for id2 in ring_b_ids[i+1:]:
                    session.run("""
                        MATCH (c1:Customer {customerID: $id1}),
                              (c2:Customer {customerID: $id2})
                        MERGE (c1)-[:SHARES_DEVICE_WITH]->(c2)
                        MERGE (c1)-[:SHARES_BANK_WITH]->(c2)
                        MERGE (c1)-[:SHARES_ADDRESS_WITH]->(c2)
                    """, id1=id1, id2=id2)

            # Duplicate Phone A
            session.run("""
                MATCH (c1:Customer {customerID: 10}),
                      (c2:Customer {customerID: 11})
                MERGE (c1)-[:SHARES_PHONE_WITH]->(c2)
            """)

            # Duplicate Phone B
            session.run("""
                MATCH (c1:Customer {customerID: 12}),
                      (c2:Customer {customerID: 13})
                MERGE (c1)-[:SHARES_PHONE_WITH]->(c2)
            """)

            # eCommerce A - all pairs
            ecom_a_ids = [16, 17, 18]
            for i, id1 in enumerate(ecom_a_ids):
                for id2 in ecom_a_ids[i+1:]:
                    session.run("""
                        MATCH (c1:Customer {customerID: $id1}),
                              (c2:Customer {customerID: $id2})
                        MERGE (c1)-[:SHARES_DEVICE_WITH]->(c2)
                    """, id1=id1, id2=id2)

            # eCommerce B - all pairs
            ecom_b_ids = [19, 20, 21]
            for i, id1 in enumerate(ecom_b_ids):
                for id2 in ecom_b_ids[i+1:]:
                    session.run("""
                        MATCH (c1:Customer {customerID: $id1}),
                              (c2:Customer {customerID: $id2})
                        MERGE (c1)-[:SHARES_DEVICE_WITH]->(c2)
                    """, id1=id1, id2=id2)

            print("SHARES_ relationships created.")

            # FraudRing nodes + MEMBER_OF
            session.run("""
                MERGE (fr:FraudRing {ringID: 'RING-FP_RING_ALPHA_A1B2'})
                SET fr.detectedAt    = date('2026-03-17'),
                    fr.memberCount   = 5,
                    fr.sharedDevice  = 'fp_ring_alpha_a1b2',
                    fr.sharedBank    = 'BARC-9921-GBP',
                    fr.totalExposure = 0.0
                WITH fr
                MATCH (c:Customer) WHERE c.customerID IN [1,2,3,4,5]
                MERGE (c)-[:MEMBER_OF]->(fr)
            """)

            session.run("""
                MERGE (fr:FraudRing {ringID: 'RING-FP_RING_GAMMA_C3D4'})
                SET fr.detectedAt    = date('2026-03-17'),
                    fr.memberCount   = 4,
                    fr.sharedDevice  = 'fp_ring_gamma_c3d4',
                    fr.sharedBank    = 'BARC-3344-GBP',
                    fr.totalExposure = 0.0
                WITH fr
                MATCH (c:Customer) WHERE c.customerID IN [6,7,8,9]
                MERGE (c)-[:MEMBER_OF]->(fr)
            """)
            print("FraudRing nodes and MEMBER_OF relationships created.")

            # Summary
            print("  Database fully seeded.")
            print("  Nodes:")
            print("    31 Customers  (21 fraud groups + 10 legitimate)")
            print("    10 Devices")
            print("    5  BankAccounts")
            print("    4  Phone nodes (duplicate phone signal)")
            print("    8  Addresses")
            print("    6  Locations   (skimming geography)")
            print("    2  FraudRings  (Ring A + Ring B)")
            print("  Fraud patterns seeded:")
            print("    1. Fraud Ring A     - IDs 1-5  (device + bank + address)")
            print("    2. Fraud Ring B     - IDs 6-9  (device + bank + address)")
            print("    3. Duplicate Phone  - IDs 10-11 and 12-13")
            print("    4. Card Skimming    - HSBC card London+Edinburgh, NatWest Manchester+Bristol")
            print("    5. Suspect eCommerce A - IDs 16-18 (same device + IP)")
            print("    6. Suspect eCommerce B - IDs 19-21 (same device + IP)")

if __name__ == "__main__":
    seed_database()
