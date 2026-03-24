-- ============================================================
-- Amazon Return Fraud Ring Detection System
-- BEMM459 — Database Technologies for Business Analytics
-- University of Exeter
-- ddl.sql — SQL Server schema (8 tables)
-- Server  : mcruebs04.isad.isadroot.ex.ac.uk
-- Database: BEMM459_SSeli
-- ============================================================

USE [BEMM459_SSeli];
GO

-- Drop tables in reverse FK order (clean slate)
IF OBJECT_ID('Investigation', 'U') IS NOT NULL DROP TABLE Investigation;
IF OBJECT_ID('FraudAlert', 'U') IS NOT NULL DROP TABLE FraudAlert;
IF OBJECT_ID('Refund',     'U') IS NOT NULL DROP TABLE Refund;
IF OBJECT_ID('[Return]',   'U') IS NOT NULL DROP TABLE [Return];
IF OBJECT_ID('[Order]',    'U') IS NOT NULL DROP TABLE [Order];
IF OBJECT_ID('PaymentMethod', 'U') IS NOT NULL DROP TABLE PaymentMethod;
IF OBJECT_ID('Product',    'U') IS NOT NULL DROP TABLE Product;
IF OBJECT_ID('ProductCategory', 'U') IS NOT NULL DROP TABLE ProductCategory;
IF OBJECT_ID('Address',    'U') IS NOT NULL DROP TABLE Address;
IF OBJECT_ID('Customer',   'U') IS NOT NULL DROP TABLE Customer;
IF OBJECT_ID('Analyst',    'U') IS NOT NULL DROP TABLE Analyst;
GO

-- ============================================================
-- 1. Analyst
-- Internal fraud prevention team. Assigned to FraudAlerts.
-- NULL AnalystID on a FraudAlert means system-generated.
-- ============================================================
CREATE TABLE Analyst (
    AnalystID   INT          IDENTITY(1,1) PRIMARY KEY,
    FirstName   VARCHAR(50)  NOT NULL,
    LastName    VARCHAR(50)  NOT NULL,
    Email       VARCHAR(100) NOT NULL UNIQUE,
    Department  VARCHAR(50)  NOT NULL DEFAULT 'Fraud Prevention',
    Role        VARCHAR(50)  NOT NULL DEFAULT 'Analyst'
);
GO

-- ============================================================
-- 2. Customer
-- Core entity. Phone, DeviceFingerprint, and IPAddress are
-- the primary fraud signals synced into Neo4j.
--
--   Phone             -> Duplicate Phone pattern
--   DeviceFingerprint -> Suspect eCommerce / Fraud Ring
--   IPAddress         -> Suspect eCommerce
--   Postcode          -> Fraud Ring geographic clustering
-- ============================================================
CREATE TABLE Customer (
    CustomerID        INT          IDENTITY(1,1) PRIMARY KEY,
    FirstName         VARCHAR(50)  NOT NULL,
    LastName          VARCHAR(50)  NOT NULL,
    Email             VARCHAR(100) NOT NULL UNIQUE,
    Phone             VARCHAR(20)  NOT NULL,          -- fraud signal: Duplicate Phone
    DeviceFingerprint VARCHAR(64)  NOT NULL,          -- fraud signal: Suspect eCommerce
    IPAddress         VARCHAR(45),                    -- fraud signal: Suspect eCommerce
    Postcode          VARCHAR(10),                    -- fraud signal: Fraud Ring clustering
    AccountCreatedAt  DATETIME     NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
-- 3. Address
-- Shipping / billing addresses. Shared postcode across
-- multiple accounts indicates geographic clustering.
-- ============================================================
CREATE TABLE Address (
    AddressID    INT          IDENTITY(1,1) PRIMARY KEY,
    CustomerID   INT          NOT NULL REFERENCES Customer(CustomerID),
    AddressLine1 VARCHAR(100) NOT NULL,
    City         VARCHAR(50)  NOT NULL,
    Postcode     VARCHAR(10)  NOT NULL,               -- fraud signal: Fraud Ring clustering
    Country      VARCHAR(50)  NOT NULL DEFAULT 'UK',
    AddressType  VARCHAR(10)  NOT NULL
        CHECK (AddressType IN ('SHIPPING', 'BILLING'))
);
GO

-- ============================================================
-- 4. Product
-- Items available for purchase. Category enables Product
-- Targeting analysis within the detection engine.
-- ============================================================
CREATE TABLE Product (
    ProductID   INT           IDENTITY(1,1) PRIMARY KEY,
    ProductName VARCHAR(100)  NOT NULL,
    Category    VARCHAR(50)   NOT NULL,
    Price       DECIMAL(10,2) NOT NULL CHECK (Price > 0),
    Description VARCHAR(200),
    StockLevel  INT           NOT NULL DEFAULT 0 CHECK (StockLevel >= 0)
);
GO

-- ============================================================
-- 5. [Order]  (bracketed — reserved word in SQL Server)
-- CardLastFour + BankRef uniquely identify a payment card.
--   Same BankRef in two distant cities within hours -> Skimming
--   Same BankRef shared across customers            -> Fraud Ring
-- ============================================================
CREATE TABLE [Order] (
    OrderID      INT           IDENTITY(1,1) PRIMARY KEY,
    CustomerID   INT           NOT NULL REFERENCES Customer(CustomerID),
    AddressID    INT           NOT NULL REFERENCES Address(AddressID),
    CardLastFour CHAR(4)       NOT NULL,              -- fraud signal: Skimming
    BankRef      VARCHAR(30)   NOT NULL,              -- fraud signal: Skimming, Fraud Ring
    OrderCity    VARCHAR(50)   NOT NULL,              -- fraud signal: Skimming (impossible travel)
    OrderDate    DATETIME      NOT NULL DEFAULT GETDATE(),
    TotalAmount  DECIMAL(10,2) NOT NULL CHECK (TotalAmount > 0),
    OrderStatus  VARCHAR(20)   NOT NULL DEFAULT 'PENDING'
        CHECK (OrderStatus IN ('PENDING', 'DELIVERED', 'CANCELLED'))
);
GO

-- ============================================================
-- 6. [Return]  (bracketed — reserved word in SQL Server)
-- High return rate and tight return timing are behavioural
-- fraud signals. ProductID enables Product Targeting analysis.
-- ============================================================
CREATE TABLE [Return] (
    ReturnID     INT           IDENTITY(1,1) PRIMARY KEY,
    OrderID      INT           NOT NULL REFERENCES [Order](OrderID),
    CustomerID   INT           NOT NULL REFERENCES Customer(CustomerID),
    ProductID    INT           NOT NULL REFERENCES Product(ProductID),
    ReturnDate   DATETIME      NOT NULL DEFAULT GETDATE(),
    ReturnReason VARCHAR(200),
    ReturnStatus VARCHAR(20)   NOT NULL DEFAULT 'PENDING'
        CHECK (ReturnStatus IN ('PENDING', 'APPROVED', 'REJECTED')),
    RefundAmount DECIMAL(10,2) NOT NULL CHECK (RefundAmount > 0)
);
GO

-- ============================================================
-- 7. Refund
-- BankRef here matches the BankRef on the originating Order.
-- Multiple customers routing to the same BankRef is the
-- Payment Cycling / Fraud Ring financial signal.
-- ============================================================
CREATE TABLE Refund (
    RefundID     INT           IDENTITY(1,1) PRIMARY KEY,
    ReturnID     INT           NOT NULL REFERENCES [Return](ReturnID),
    BankRef      VARCHAR(30)   NOT NULL,              -- fraud signal: Fraud Ring
    RefundAmount DECIMAL(10,2) NOT NULL CHECK (RefundAmount > 0),
    RefundDate   DATETIME      NOT NULL DEFAULT GETDATE(),
    RefundStatus VARCHAR(20)   NOT NULL DEFAULT 'PENDING'
        CHECK (RefundStatus IN ('PENDING', 'PROCESSED', 'FAILED'))
);
GO

-- ============================================================
-- 8. FraudAlert
-- Raised automatically by the Python detection system
-- (AnalystID = NULL) or manually by an analyst.
-- AlertType maps to one of the four fraud detection patterns.
-- FraudScore is a composite risk score; threshold >= 5.0.
-- ============================================================
CREATE TABLE FraudAlert (
    FraudAlertID INT           IDENTITY(1,1) PRIMARY KEY,
    CustomerID   INT           NOT NULL REFERENCES Customer(CustomerID),
    AnalystID    INT                    REFERENCES Analyst(AnalystID),  -- NULL = system
    AlertType    VARCHAR(30)   NOT NULL
        CHECK (AlertType IN (
            'FRAUD_RING',          -- shared address, bank, or phone across accounts
            'DUPLICATE_PHONE',     -- same phone number on two+ customer accounts
            'SKIMMING',            -- same card used in distant cities within hours
            'SUSPECT_ECOMMERCE',   -- same device fingerprint or IP across accounts
            'HIGH_RETURN_RATE'     -- behavioural: >50% of orders returned
        )),
    DetectedAt   DATETIME      NOT NULL DEFAULT GETDATE(),
    FraudScore   DECIMAL(5,2),
    Status       VARCHAR(20)   NOT NULL DEFAULT 'OPEN'
        CHECK (Status IN ('OPEN', 'CLOSED', 'ESCALATED')),
    Notes        VARCHAR(500)
);
GO

-- Indexes — support fraud detection and reporting queries
DROP INDEX IF EXISTS IX_Customer_Phone ON Customer;
CREATE INDEX IX_Customer_Phone ON Customer(Phone);
CREATE INDEX IX_Customer_Device      ON Customer(DeviceFingerprint);
CREATE INDEX IX_Customer_Postcode    ON Customer(Postcode);
CREATE INDEX IX_Order_BankRef        ON [Order](BankRef, OrderDate);
CREATE INDEX IX_Order_CustomerDate   ON [Order](CustomerID, OrderDate);
CREATE INDEX IX_Return_CustomerDate  ON [Return](CustomerID, ReturnDate);
CREATE INDEX IX_Refund_BankRef       ON Refund(BankRef, RefundDate);
CREATE INDEX IX_Address_Postcode     ON Address(Postcode);
GO

PRINT 'DDL complete — 8 tables created with indexes.';
