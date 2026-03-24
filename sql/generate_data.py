#!/usr/bin/env python3
"""
generate_data.py
Generates dml.sql with 500 customers and realistic data for the
Amazon Return Fraud Ring Detection System (BEMM459 — University of Exeter).

Two examples of each fraud pattern are embedded:
  Pattern 1 — Fraud Ring        : Ring A (C1-C5)  and Ring B (C6-C9)
  Pattern 2 — Duplicate Phone   : Pair A (C10-C11) and Pair B (C12-C13)
  Pattern 3 — Skimming          : C14 and C15 each have a skimming incident
  Pattern 4 — Suspect eCommerce : Group A (C16-C18) and Group B (C19-C21)
  Legitimate customers          : C22-C500

Usage : python generate_data.py
Output: dml.sql
"""

import random
from datetime import datetime, timedelta
from collections import defaultdict

random.seed(42)

# ── Fraud constants ───────────────────────────────────────────────────────────
RING_A_IDS   = list(range(1,  6))   # 5 members
RING_B_IDS   = list(range(6,  10))  # 4 members
DUP_PHONE_A  = [10, 11]
DUP_PHONE_B  = [12, 13]
SKIM_IDS     = [14, 15]
ECOM_A_IDS   = [16, 17, 18]
ECOM_B_IDS   = [19, 20, 21]

RING_A_DEVICE  = 'fp_ring_alpha_a1b2'
RING_A_BANK    = 'BARC-9921-GBP'
RING_A_POST    = 'EC1A 1BB'
RING_A_IP_PFX  = '192.168.10.'

RING_B_DEVICE  = 'fp_ring_gamma_c3d4'
RING_B_BANK    = 'BARC-3344-GBP'
RING_B_POST    = 'E1 6RF'
RING_B_IP_PFX  = '192.168.20.'

PHONE_A = '07700900999'
PHONE_B = '07700901234'

SKIM_BANK_14 = 'BARC-7788-GBP'  # London -> Edinburgh, 45 min gap
SKIM_BANK_15 = 'BARC-5566-GBP'  # Manchester -> Bristol, 60 min gap

ECOM_A_DEVICE = 'fp_shared_ecom_a'
ECOM_A_IP     = '85.10.20.30'
ECOM_B_DEVICE = 'fp_shared_ecom_b'
ECOM_B_IP     = '91.22.33.44'

# ── Reference data ────────────────────────────────────────────────────────────
FIRST_NAMES = [
    'James','Oliver','Harry','George','Noah','Charlie','Jack','Leo','Freddie','Alfie',
    'Emily','Olivia','Amelia','Isla','Ava','Mia','Isabella','Sophia','Grace','Lily',
    'Mohammed','Aiden','Lucas','Ethan','Mason','Logan','Ryan','Dylan','Callum','Liam',
    'Priya','Sian','Chloe','Hannah','Zara','Thomas','William','Benjamin','Samuel','Daniel',
    'Emma','Charlotte','Alice','Jessica','Lauren','Sophie','Rebecca','Laura','Amy','Sarah',
    'Michael','David','Robert','Richard','Joseph','Andrew','Mark','Paul','Steven','Kevin',
]
LAST_NAMES = [
    'Smith','Jones','Williams','Taylor','Brown','Davies','Evans','Wilson','Thomas',
    'Roberts','Johnson','White','Hall','Martin','Thompson','Lewis','Clarke','Walker',
    'Wright','Collins','Khan','Patel','Ahmed','Singh','Ali','Hussain','Bennett',
    'Cooper','Richardson','Cox','Morgan','Hughes','Price','Ward','Wood','Jackson',
    'Harris','Young','King','Scott','Green','Adams','Baker','Nelson','Carter','Mitchell',
    'Perez','Turner','Phillips','Campbell','Parker','Edwards','Collins','Stewart','Morris',
]
CITIES_POSTCODES = [
    ('London','SW1A 2AA'), ('London','WC2N 5DU'), ('London','N1 9GU'),
    ('Manchester','M1 1AE'), ('Birmingham','B1 1BB'), ('Leeds','LS1 1BA'),
    ('Glasgow','G1 1AF'),   ('Liverpool','L1 1AA'), ('Edinburgh','EH1 1BB'),
    ('Bristol','BS1 1AA'),  ('Sheffield','S1 2HH'), ('Leicester','LE1 1AA'),
    ('Coventry','CV1 1AA'), ('Bradford','BD1 1AA'), ('Nottingham','NG1 1AA'),
    ('Reading','RG1 1AA'),  ('Cardiff','CF10 1AA'), ('Oxford','OX1 2JD'),
    ('Cambridge','CB2 1TN'),('Southampton','SO14 0YG'),
]
STREETS = [
    'High Street','Church Lane','Victoria Road','King Street','Queen Street',
    'Park Avenue','Station Road','Mill Lane','Green Lane','New Road',
    'Bridge Street','North Road','South Street','East Avenue','West Close',
    'Castle Street','Abbey Road','Market Street','Church Road','London Road',
]
CARD_TYPES    = ['VISA', 'MASTERCARD', 'AMEX']
RETURN_REASONS = [
    'Item not as described','Received wrong item','Item arrived damaged',
    'No longer needed','Found better price elsewhere','Item too small',
    'Item too large','Poor quality','Missing parts','Does not work as expected',
]

# Unique pools (exclude fraud constants)
_raw_banks = [f"BARC-{random.randint(1000,9999)}-GBP" for _ in range(1000)]
BANK_POOL  = list(set(_raw_banks) - {RING_A_BANK, RING_B_BANK, SKIM_BANK_14, SKIM_BANK_15})

_raw_fps   = [f"fp_{random.randint(0x100000,0xFFFFFF):06x}_{random.randint(0x1000,0xFFFF):04x}" for _ in range(1000)]
FP_POOL    = list(set(_raw_fps) - {RING_A_DEVICE, RING_B_DEVICE, ECOM_A_DEVICE, ECOM_B_DEVICE})

IP_POOL    = [
    f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
    for _ in range(1000)
]

# ── Static tables ─────────────────────────────────────────────────────────────
PRODUCTS = [
    (1,  'Samsung Galaxy S24',         'Electronics', 749.99),
    (2,  'Apple AirPods Pro',          'Electronics', 249.99),
    (3,  'Sony PlayStation 5',         'Electronics', 499.99),
    (4,  'MacBook Air M2',             'Electronics', 1099.99),
    (5,  'Dyson V15 Vacuum',           'Electronics', 599.99),
    (6,  'Nintendo Switch OLED',       'Electronics', 309.99),
    (7,  'Bose QuietComfort 45',       'Electronics', 279.99),
    (8,  'GoPro Hero 12',              'Electronics', 399.99),
    (9,  'iPhone 15 Pro',              'Electronics', 999.99),
    (10, 'Amazon Echo Dot',            'Electronics', 49.99),
    (11, 'Nike Air Max 270',           'Clothing',    134.99),
    (12, "Levi's 501 Jeans",           'Clothing',    69.99),
    (13, 'North Face Jacket',          'Clothing',    199.99),
    (14, 'Adidas Hoodie',              'Clothing',    59.99),
    (15, 'Timberland Boots',           'Clothing',    159.99),
    (16, 'Atomic Habits (Book)',        'Books',       14.99),
    (17, 'Harry Potter Box Set',        'Books',       49.99),
    (18, 'Instant Pot Duo 7-in-1',     'Kitchen',     89.99),
    (19, 'Nespresso Vertuo Next',       'Kitchen',    129.99),
    (20, 'Garmin Forerunner 265',       'Sports',     349.99),
    (21, 'Yoga Mat Premium',            'Sports',      39.99),
    (22, 'LEGO Technic Set',            'Toys',        89.99),
    (23, 'Monopoly Board Game',         'Toys',        29.99),
    (24, 'Dyson Airwrap',               'Beauty',     479.99),
    (25, 'Logitech MX Master 3 Mouse',  'Office',      89.99),
]
ELECTRONICS_IDS = [p[0] for p in PRODUCTS if p[2] == 'Electronics']

NOW = datetime(2026, 3, 10)

def rand_dt(start, end):
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(delta, 1)))

def fmt_dt(dt):
    return dt.strftime("'%Y-%m-%d %H:%M:%S'")

def q(s):
    return "'" + str(s).replace("'", "''") + "'"


# ── Generator ─────────────────────────────────────────────────────────────────
def generate():
    lines = []
    def ln(s=''):
        lines.append(s)

    ln("-- ============================================================")
    ln("-- Amazon Return Fraud Ring Detection System")
    ln("-- BEMM459 — Database Technologies for Business Analytics")
    ln("-- University of Exeter")
    ln("-- dml.sql  —  Sample data (500 customers, ~5 500 rows total)")
    ln("-- Generated by generate_data.py")
    ln("--")
    ln("-- Fraud patterns:")
    ln("--   Ring A      : CustomerIDs 1-5   (device fp_ring_alpha, bank BARC-9921-GBP)")
    ln("--   Ring B      : CustomerIDs 6-9   (device fp_ring_gamma, bank BARC-3344-GBP)")
    ln("--   Dup Phone A : CustomerIDs 10-11 (phone 07700900999)")
    ln("--   Dup Phone B : CustomerIDs 12-13 (phone 07700901234)")
    ln("--   Skimming    : CustomerID 14 (London->Edinburgh) and 15 (Manchester->Bristol)")
    ln("--   eCommerce A : CustomerIDs 16-18 (device fp_shared_ecom_a, IP 85.10.20.30)")
    ln("--   eCommerce B : CustomerIDs 19-21 (device fp_shared_ecom_b, IP 91.22.33.44)")
    ln("-- ============================================================")
    ln()
    ln("USE [BEMM459_SSeli];")
    ln("GO")
    ln()

    # ── Analyst ───────────────────────────────────────────────────────────────
    ln("-- Analyst")
    ln("SET IDENTITY_INSERT Analyst ON;")
    for row in [
        (1, 'Sarah',  'Mitchell', 'sarah.mitchell@amazon-fraud.co.uk', 'Fraud Prevention', 'Senior Analyst'),
        (2, 'James',  'Cooper',   'james.cooper@amazon-fraud.co.uk',   'Fraud Prevention', 'Junior Analyst'),
        (3, 'Priya',  'Sharma',   'priya.sharma@amazon-fraud.co.uk',   'Fraud Prevention', 'Analyst'),
    ]:
        ln(f"INSERT INTO Analyst (AnalystID,FirstName,LastName,Email,Department,Role) "
           f"VALUES ({row[0]},{q(row[1])},{q(row[2])},{q(row[3])},{q(row[4])},{q(row[5])});")
    ln("SET IDENTITY_INSERT Analyst OFF;")
    ln("GO")
    ln()

    # ── Customer ──────────────────────────────────────────────────────────────
    customers = []  # (id, fn, ln, email, phone, fp, ip, postcode, created_at)
    used_emails = set()
    fp_iter  = iter(FP_POOL)
    ip_iter  = iter(IP_POOL)
    bank_iter = iter(BANK_POOL)

    def make_email(fn, ln_, suffix, domain):
        base = f"{fn.lower()}.{ln_.lower()}{suffix}@{domain}"
        if base not in used_emails:
            used_emails.add(base)
            return base
        alt = f"{fn.lower()}{ln_.lower()}{suffix}_{random.randint(10,99)}@{domain}"
        used_emails.add(alt)
        return alt

    domains = ['gmail.com','hotmail.co.uk','outlook.com','yahoo.co.uk','icloud.com']

    def add_customer(cid, fn, ln_, phone, fp, ip, postcode, created):
        email = make_email(fn, ln_, cid, random.choice(domains))
        customers.append((cid, fn, ln_, email, phone, fp, ip, postcode, created))

    # Ring A (C1-C5) — new accounts, same device/bank/postcode
    for i in RING_A_IDS:
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        created = rand_dt(NOW - timedelta(days=28), NOW - timedelta(days=5))
        add_customer(i, fn, ln_, f"077009001{i:02d}", RING_A_DEVICE,
                     RING_A_IP_PFX + str(i), RING_A_POST, created)

    # Ring B (C6-C9) — new accounts, same device/bank/postcode
    for i, cid in enumerate(RING_B_IDS):
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        created = rand_dt(NOW - timedelta(days=21), NOW - timedelta(days=3))
        add_customer(cid, fn, ln_, f"077009002{i:02d}", RING_B_DEVICE,
                     RING_B_IP_PFX + str(i + 1), RING_B_POST, created)

    # Duplicate phone A (C10-C11)
    for cid in DUP_PHONE_A:
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        city, pc = random.choice(CITIES_POSTCODES)
        created = rand_dt(NOW - timedelta(days=500), NOW - timedelta(days=60))
        add_customer(cid, fn, ln_, PHONE_A, next(fp_iter), next(ip_iter), pc, created)

    # Duplicate phone B (C12-C13)
    for cid in DUP_PHONE_B:
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        city, pc = random.choice(CITIES_POSTCODES)
        created = rand_dt(NOW - timedelta(days=400), NOW - timedelta(days=50))
        add_customer(cid, fn, ln_, PHONE_B, next(fp_iter), next(ip_iter), pc, created)

    # Skimming (C14-C15)
    for cid in SKIM_IDS:
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        city, pc = random.choice(CITIES_POSTCODES)
        created = rand_dt(NOW - timedelta(days=730), NOW - timedelta(days=90))
        add_customer(cid, fn, ln_, f"077009003{cid:02d}", next(fp_iter),
                     next(ip_iter), pc, created)

    # Suspect eCommerce A (C16-C18)
    for cid in ECOM_A_IDS:
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        city, pc = random.choice(CITIES_POSTCODES)
        created = rand_dt(NOW - timedelta(days=300), NOW - timedelta(days=30))
        add_customer(cid, fn, ln_, f"077009004{cid:02d}", ECOM_A_DEVICE,
                     ECOM_A_IP, pc, created)

    # Suspect eCommerce B (C19-C21)
    for cid in ECOM_B_IDS:
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        city, pc = random.choice(CITIES_POSTCODES)
        created = rand_dt(NOW - timedelta(days=250), NOW - timedelta(days=20))
        add_customer(cid, fn, ln_, f"077009005{cid:02d}", ECOM_B_DEVICE,
                     ECOM_B_IP, pc, created)

    # Legitimate (C22-C500)
    for cid in range(22, 501):
        fn, ln_ = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        city, pc = random.choice(CITIES_POSTCODES)
        phone = f"07{random.randint(700000000,799999999)}"
        created = rand_dt(NOW - timedelta(days=1095), NOW - timedelta(days=60))
        add_customer(cid, fn, ln_, phone, next(fp_iter), next(ip_iter), pc, created)

    ln(f"-- Customer ({len(customers)} rows)")
    ln("SET IDENTITY_INSERT Customer ON;")
    for cid, fn, ln_, email, phone, fp, ip, pc, created in customers:
        ln(f"INSERT INTO Customer "
           f"(CustomerID,FirstName,LastName,Email,Phone,DeviceFingerprint,IPAddress,Postcode,AccountCreatedAt) "
           f"VALUES ({cid},{q(fn)},{q(ln_)},{q(email)},{q(phone)},{q(fp)},{q(ip)},{q(pc)},{fmt_dt(created)});")
    ln("SET IDENTITY_INSERT Customer OFF;")
    ln("GO")
    ln()

    # ── Address ───────────────────────────────────────────────────────────────
    addresses = []   # (addr_id, cust_id, line1, city, postcode, type)
    cust_ship = {}   # cust_id -> addr_id
    addr_id   = 1

    cust_map = {c[0]: c for c in customers}   # id -> tuple

    for cid, fn, ln_, email, phone, fp, ip, pc, created in customers:
        if cid in RING_A_IDS:
            city, apc = 'London', RING_A_POST
        elif cid in RING_B_IDS:
            city, apc = 'London', RING_B_POST
        else:
            city, apc = random.choice(CITIES_POSTCODES)
        line1 = f"{random.randint(1,200)} {random.choice(STREETS)}"
        addresses.append((addr_id, cid, line1, city, apc, 'SHIPPING'))
        cust_ship[cid] = addr_id
        addr_id += 1
        if random.random() < 0.25:   # 25% have a separate billing address
            bc, bpc = random.choice(CITIES_POSTCODES)
            bl1 = f"{random.randint(1,200)} {random.choice(STREETS)}"
            addresses.append((addr_id, cid, bl1, bc, bpc, 'BILLING'))
            addr_id += 1

    ln(f"-- Address ({len(addresses)} rows)")
    ln("SET IDENTITY_INSERT Address ON;")
    for aid, cid, line1, city, pc, atype in addresses:
        ln(f"INSERT INTO Address "
           f"(AddressID,CustomerID,AddressLine1,City,Postcode,Country,AddressType) "
           f"VALUES ({aid},{cid},{q(line1)},{q(city)},{q(pc)},'UK',{q(atype)});")
    ln("SET IDENTITY_INSERT Address OFF;")
    ln("GO")
    ln()

    # ── Product ───────────────────────────────────────────────────────────────
    ln(f"-- Product ({len(PRODUCTS)} rows)")
    ln("SET IDENTITY_INSERT Product ON;")
    for pid, pname, cat, price in PRODUCTS:
        stock = random.randint(20, 300)
        ln(f"INSERT INTO Product (ProductID,ProductName,Category,Price,StockLevel) "
           f"VALUES ({pid},{q(pname)},{q(cat)},{price},{stock});")
    ln("SET IDENTITY_INSERT Product OFF;")
    ln("GO")
    ln()

    # ── Order ─────────────────────────────────────────────────────────────────
    orders   = []   # (oid, cid, aid, card4, bankref, city, odt, amt, status)
    cust_ord = defaultdict(list)   # cid -> [(oid, odt, bankref)]
    order_id = 1

    # Ring A (C1-C5): 10-14 orders each, mostly electronics, recent dates
    for cid in RING_A_IDS:
        aid = cust_ship[cid]
        for _ in range(random.randint(10, 14)):
            prod = random.choice([p for p in PRODUCTS if p[0] in ELECTRONICS_IDS]
                                 if random.random() < 0.8 else PRODUCTS)
            odt = rand_dt(NOW - timedelta(days=85), NOW - timedelta(days=2))
            amt = round(prod[3] * random.randint(1, 2), 2)
            orders.append((order_id, cid, aid, f"{random.randint(1000,9999)}",
                           RING_A_BANK, 'London', odt, amt, 'DELIVERED'))
            cust_ord[cid].append((order_id, odt, RING_A_BANK))
            order_id += 1

    # Ring B (C6-C9): same pattern
    for cid in RING_B_IDS:
        aid = cust_ship[cid]
        for _ in range(random.randint(10, 14)):
            prod = random.choice([p for p in PRODUCTS if p[0] in ELECTRONICS_IDS]
                                 if random.random() < 0.8 else PRODUCTS)
            odt = rand_dt(NOW - timedelta(days=60), NOW - timedelta(days=2))
            amt = round(prod[3] * random.randint(1, 2), 2)
            orders.append((order_id, cid, aid, f"{random.randint(1000,9999)}",
                           RING_B_BANK, 'London', odt, amt, 'DELIVERED'))
            cust_ord[cid].append((order_id, odt, RING_B_BANK))
            order_id += 1

    # Duplicate phone & eCommerce groups: normal orders with their own bank refs
    for cid in DUP_PHONE_A + DUP_PHONE_B + ECOM_A_IDS + ECOM_B_IDS:
        aid = cust_ship[cid]
        br  = next(bank_iter)
        city_pc = random.choice(CITIES_POSTCODES)
        city = city_pc[0]
        for _ in range(random.randint(4, 8)):
            prod = random.choice(PRODUCTS)
            odt = rand_dt(NOW - timedelta(days=300), NOW - timedelta(days=5))
            amt = round(prod[3] * random.randint(1, 2), 2)
            orders.append((order_id, cid, aid, f"{random.randint(1000,9999)}",
                           br, city, odt, amt, 'DELIVERED'))
            cust_ord[cid].append((order_id, odt, br))
            order_id += 1

    # Skimming C14: normal orders + 2 skimming orders same day (London then Edinburgh)
    skim_base_dt = NOW - timedelta(days=10)
    c14_aid = cust_ship[14]
    c14_br  = SKIM_BANK_14
    c14_card = f"{random.randint(1000,9999)}"
    # normal orders
    for _ in range(4):
        prod = random.choice(PRODUCTS)
        odt = rand_dt(NOW - timedelta(days=200), skim_base_dt - timedelta(days=2))
        amt = round(prod[3], 2)
        city_p = random.choice(CITIES_POSTCODES)[0]
        orders.append((order_id, 14, c14_aid, c14_card, c14_br, city_p, odt, amt, 'DELIVERED'))
        cust_ord[14].append((order_id, odt, c14_br))
        order_id += 1
    # Skimming orders: London 09:00, Edinburgh 09:45 — 45 min gap, impossible travel
    odt_lon = skim_base_dt.replace(hour=9, minute=0, second=0)
    odt_edi = skim_base_dt.replace(hour=9, minute=45, second=0)
    orders.append((order_id, 14, c14_aid, c14_card, c14_br, 'London', odt_lon, 749.99, 'DELIVERED'))
    cust_ord[14].append((order_id, odt_lon, c14_br))
    order_id += 1
    orders.append((order_id, 14, c14_aid, c14_card, c14_br, 'Edinburgh', odt_edi, 499.99, 'DELIVERED'))
    cust_ord[14].append((order_id, odt_edi, c14_br))
    order_id += 1

    # Skimming C15: Manchester 10:00, Bristol 11:00 — 60 min gap, ~170 miles
    skim_base_dt2 = NOW - timedelta(days=8)
    c15_aid = cust_ship[15]
    c15_br  = SKIM_BANK_15
    c15_card = f"{random.randint(1000,9999)}"
    for _ in range(4):
        prod = random.choice(PRODUCTS)
        odt = rand_dt(NOW - timedelta(days=180), skim_base_dt2 - timedelta(days=2))
        amt = round(prod[3], 2)
        city_p = random.choice(CITIES_POSTCODES)[0]
        orders.append((order_id, 15, c15_aid, c15_card, c15_br, city_p, odt, amt, 'DELIVERED'))
        cust_ord[15].append((order_id, odt, c15_br))
        order_id += 1
    odt_man = skim_base_dt2.replace(hour=10, minute=0, second=0)
    odt_brs = skim_base_dt2.replace(hour=11, minute=0, second=0)
    orders.append((order_id, 15, c15_aid, c15_card, c15_br, 'Manchester', odt_man, 599.99, 'DELIVERED'))
    cust_ord[15].append((order_id, odt_man, c15_br))
    order_id += 1
    orders.append((order_id, 15, c15_aid, c15_card, c15_br, 'Bristol', odt_brs, 399.99, 'DELIVERED'))
    cust_ord[15].append((order_id, odt_brs, c15_br))
    order_id += 1

    # Legitimate customers (C22-C500): 5-10 orders each
    for cid, fn, ln_, email, phone, fp, ip, pc, created in customers:
        if cid < 22:
            continue
        aid  = cust_ship[cid]
        br   = next(bank_iter)
        city = random.choice(CITIES_POSTCODES)[0]
        n    = random.randint(5, 10)
        for _ in range(n):
            prod   = random.choice(PRODUCTS)
            odt    = rand_dt(created + timedelta(days=3), NOW - timedelta(days=3))
            amt    = round(prod[3] * random.randint(1, 2), 2)
            status = random.choices(['DELIVERED','CANCELLED'], weights=[93,7])[0]
            orders.append((order_id, cid, aid, f"{random.randint(1000,9999)}",
                           br, city, odt, amt, status))
            cust_ord[cid].append((order_id, odt, br))
            order_id += 1

    ln(f"-- [Order] ({len(orders)} rows)")
    ln("SET IDENTITY_INSERT [Order] ON;")
    for oid, cid, aid, card4, br, city, odt, amt, st in orders:
        ln(f"INSERT INTO [Order] "
           f"(OrderID,CustomerID,AddressID,CardLastFour,BankRef,OrderCity,OrderDate,TotalAmount,OrderStatus) "
           f"VALUES ({oid},{cid},{aid},{q(card4)},{q(br)},{q(city)},{fmt_dt(odt)},{amt},{q(st)});")
    ln("SET IDENTITY_INSERT [Order] OFF;")
    ln("GO")
    ln()

    # ── Return ────────────────────────────────────────────────────────────────
    returns  = []   # (rid, oid, cid, pid, rdt, reason, status, amt)
    ret_id   = 1
    ord_ret  = {}   # oid -> rid (for refund FK)

    ring_all = set(RING_A_IDS + RING_B_IDS)

    # Ring members: 60-70% return rate, return within 12-48 hrs, electronics only
    for cid in ring_all:
        ring_orders = sorted(cust_ord[cid], key=lambda x: x[1])
        n_ret = int(len(ring_orders) * random.uniform(0.60, 0.70))
        chosen = sorted(random.sample(ring_orders, n_ret), key=lambda x: x[1])
        base = random.uniform(80, 150)
        for idx, (oid, odt, br) in enumerate(chosen):
            rdt    = odt + timedelta(hours=random.randint(12, 47))
            pid    = random.choice(ELECTRONICS_IDS)
            factor = 1 + idx * 0.12   # escalating amounts
            amt    = round(min(base * factor, 999.99), 2)
            reason = random.choice(RETURN_REASONS)
            returns.append((ret_id, oid, cid, pid, rdt, reason, 'APPROVED', amt))
            ord_ret[oid] = (ret_id, rdt, cid, amt, br)
            ret_id += 1

    # All other fraud customers: normal return rate
    other_fraud = (set(DUP_PHONE_A + DUP_PHONE_B + SKIM_IDS + ECOM_A_IDS + ECOM_B_IDS)
                   - ring_all)
    for cid in other_fraud:
        o_list = cust_ord[cid]
        n_ret  = max(1, int(len(o_list) * 0.20))
        for oid, odt, br in random.sample(o_list, min(n_ret, len(o_list))):
            rdt    = odt + timedelta(days=random.randint(3, 14))
            rdt    = min(rdt, NOW - timedelta(hours=1))
            prod   = random.choice(PRODUCTS)
            amt    = round(prod[3] * random.uniform(0.8, 1.0), 2)
            reason = random.choice(RETURN_REASONS)
            status = random.choices(['APPROVED','REJECTED','PENDING'], weights=[75,10,15])[0]
            returns.append((ret_id, oid, cid, prod[0], rdt, reason, status, amt))
            ord_ret[oid] = (ret_id, rdt, cid, amt, br)
            ret_id += 1

    # Legitimate customers: 10-15% return rate
    for cid, *_ in customers:
        if cid < 22:
            continue
        o_list = cust_ord[cid]
        if not o_list:
            continue
        n_ret = max(1, int(len(o_list) * random.uniform(0.10, 0.15)))
        for oid, odt, br in random.sample(o_list, min(n_ret, len(o_list))):
            rdt    = odt + timedelta(days=random.randint(3, 21))
            rdt    = min(rdt, NOW - timedelta(hours=1))
            prod   = random.choice(PRODUCTS)
            amt    = round(prod[3] * random.uniform(0.8, 1.0), 2)
            reason = random.choice(RETURN_REASONS)
            status = random.choices(['APPROVED','REJECTED','PENDING'], weights=[75,10,15])[0]
            returns.append((ret_id, oid, cid, prod[0], rdt, reason, status, amt))
            ord_ret[oid] = (ret_id, rdt, cid, amt, br)
            ret_id += 1

    ln(f"-- [Return] ({len(returns)} rows)")
    ln("SET IDENTITY_INSERT [Return] ON;")
    for rid, oid, cid, pid, rdt, reason, status, amt in returns:
        ln(f"INSERT INTO [Return] "
           f"(ReturnID,OrderID,CustomerID,ProductID,ReturnDate,ReturnReason,ReturnStatus,RefundAmount) "
           f"VALUES ({rid},{oid},{cid},{pid},{fmt_dt(rdt)},{q(reason)},{q(status)},{amt});")
    ln("SET IDENTITY_INSERT [Return] OFF;")
    ln("GO")
    ln()

    # ── Refund ────────────────────────────────────────────────────────────────
    refunds  = []   # (rfid, rid, bankref, amt, rfdt, status)
    rfund_id = 1
    ord_bank = {oid: br for oid, cid, aid, card4, br, city, odt, amt, st in orders}

    for rid, oid, cid, pid, rdt, reason, status, amt in returns:
        if status != 'APPROVED':
            continue
        br = ord_bank.get(oid, 'UNKNOWN')
        if cid in ring_all:
            rfdt   = rdt + timedelta(hours=random.randint(1, 6))
            rfstat = 'PROCESSED'
        else:
            rfdt   = rdt + timedelta(days=random.randint(1, 7))
            rfstat = random.choices(['PROCESSED','PENDING','FAILED'], weights=[80,15,5])[0]
        refunds.append((rfund_id, rid, br, amt, rfdt, rfstat))
        rfund_id += 1

    ln(f"-- Refund ({len(refunds)} rows)")
    ln("SET IDENTITY_INSERT Refund ON;")
    for rfid, rid, br, amt, rfdt, rfstat in refunds:
        ln(f"INSERT INTO Refund "
           f"(RefundID,ReturnID,BankRef,RefundAmount,RefundDate,RefundStatus) "
           f"VALUES ({rfid},{rid},{q(br)},{amt},{fmt_dt(rfdt)},{q(rfstat)});")
    ln("SET IDENTITY_INSERT Refund OFF;")
    ln("GO")
    ln()

    # ── FraudAlert ────────────────────────────────────────────────────────────
    alerts = []   # (aid, cid, analyst_id, type, detected, score, status, notes)
    alert_id = 1

    def make_ring_exposure(cids):
        total = sum(r[7] for r in returns if r[2] in set(cids) and r[6] == 'APPROVED')
        return round(total, 2)

    ring_a_exp = make_ring_exposure(RING_A_IDS)
    ring_b_exp = make_ring_exposure(RING_B_IDS)

    for cid in RING_A_IDS:
        alerts.append((alert_id, cid, None, 'FRAUD_RING',
                        NOW - timedelta(days=random.randint(1,10)),
                        9.5, 'OPEN',
                        f"Member of RING-A. Shared device {RING_A_DEVICE}, "
                        f"bank {RING_A_BANK}. Ring exposure: £{ring_a_exp:,.2f}. "
                        f"Members: {RING_A_IDS}."))
        alert_id += 1

    for cid in RING_B_IDS:
        alerts.append((alert_id, cid, None, 'FRAUD_RING',
                        NOW - timedelta(days=random.randint(1,7)),
                        9.5, 'OPEN',
                        f"Member of RING-B. Shared device {RING_B_DEVICE}, "
                        f"bank {RING_B_BANK}. Ring exposure: £{ring_b_exp:,.2f}. "
                        f"Members: {RING_B_IDS}."))
        alert_id += 1

    for pair, ph in [(DUP_PHONE_A, PHONE_A), (DUP_PHONE_B, PHONE_B)]:
        for cid in pair:
            other = [x for x in pair if x != cid][0]
            alerts.append((alert_id, cid, 1, 'DUPLICATE_PHONE',
                           NOW - timedelta(days=random.randint(2,15)),
                           5.0, 'OPEN',
                           f"Phone {ph} also registered to Customer #{other}."))
            alert_id += 1

    alerts.append((alert_id, 14, 2, 'SKIMMING',
                   NOW - timedelta(days=9), 8.0, 'ESCALATED',
                   f"Card {SKIM_BANK_14} used in London at 09:00 and Edinburgh at 09:45 "
                   f"on {(NOW - timedelta(days=10)).strftime('%Y-%m-%d')} — "
                   f"45 minute gap, ~400 miles. Card compromise suspected."))
    alert_id += 1

    alerts.append((alert_id, 15, 2, 'SKIMMING',
                   NOW - timedelta(days=7), 8.0, 'ESCALATED',
                   f"Card {SKIM_BANK_15} used in Manchester at 10:00 and Bristol at 11:00 "
                   f"on {(NOW - timedelta(days=8)).strftime('%Y-%m-%d')} — "
                   f"60 minute gap, ~170 miles. Card compromise suspected."))
    alert_id += 1

    for cid in ECOM_A_IDS:
        alerts.append((alert_id, cid, None, 'SUSPECT_ECOMMERCE',
                       NOW - timedelta(days=random.randint(3,20)),
                       6.5, 'OPEN',
                       f"Device {ECOM_A_DEVICE} and IP {ECOM_A_IP} shared across "
                       f"Customer IDs {ECOM_A_IDS}. Likely coordinated accounts."))
        alert_id += 1

    for cid in ECOM_B_IDS:
        alerts.append((alert_id, cid, None, 'SUSPECT_ECOMMERCE',
                       NOW - timedelta(days=random.randint(2,15)),
                       6.5, 'OPEN',
                       f"Device {ECOM_B_DEVICE} and IP {ECOM_B_IP} shared across "
                       f"Customer IDs {ECOM_B_IDS}. Likely coordinated accounts."))
        alert_id += 1

    # A handful of legitimate high-returners flagged as false positives
    fp_cands = [cid for cid, *_ in customers if cid >= 22][:8]
    for cid in fp_cands:
        alerts.append((alert_id, cid, 3, 'HIGH_RETURN_RATE',
                       NOW - timedelta(days=random.randint(5,30)),
                       3.5, 'OPEN',
                       "High return rate flagged by automated rule. Under review — "
                       "may be legitimate."))
        alert_id += 1

    ln(f"-- FraudAlert ({len(alerts)} rows)")
    ln("SET IDENTITY_INSERT FraudAlert ON;")
    for faid, cid, analyst_id, atype, detected, score, status, notes in alerts:
        an = str(analyst_id) if analyst_id else 'NULL'
        ln(f"INSERT INTO FraudAlert "
           f"(FraudAlertID,CustomerID,AnalystID,AlertType,DetectedAt,FraudScore,Status,Notes) "
           f"VALUES ({faid},{cid},{an},{q(atype)},{fmt_dt(detected)},{score},{q(status)},{q(notes[:499])});")
    ln("SET IDENTITY_INSERT FraudAlert OFF;")
    ln("GO")
    ln()

    # ── Summary ───────────────────────────────────────────────────────────────
    totals = {
        'Analyst':     3,
        'Customer':    len(customers),
        'Address':     len(addresses),
        'Product':     len(PRODUCTS),
        '[Order]':     len(orders),
        '[Return]':    len(returns),
        'Refund':      len(refunds),
        'FraudAlert':  len(alerts),
    }
    grand = sum(totals.values())
    ln("-- ============================================================")
    ln("-- Row count summary:")
    for tbl, cnt in totals.items():
        ln(f"--   {tbl:<14} {cnt:>5} rows")
    ln(f"--   {'TOTAL':<14} {grand:>5} rows")
    ln("-- ============================================================")
    ln(f"PRINT 'DML complete — {grand} rows inserted.';")

    return '\n'.join(lines)


if __name__ == '__main__':
    sql = generate()
    with open('dml.sql', 'w', encoding='utf-8') as f:
        f.write(sql)
    print("dml.sql generated successfully.")
    print()
    print("Next step — run on SQL Server:")
    print('  sqlcmd -S mcruebs04.isad.isadroot.ex.ac.uk -U SSeli -d "BEMM459_SSeli" -i dml.sql')
