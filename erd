# Entity Relationship Diagram — Amazon Return Fraud Ring Detection System
## BEMM459 — University of Exeter

```mermaid
erDiagram

    Analyst {
        int     AnalystID       PK
        varchar FirstName
        varchar LastName
        varchar Email           UK
        varchar Department
        varchar Role
    }

    Customer {
        int     CustomerID      PK
        varchar FirstName
        varchar LastName
        varchar Email           UK
        varchar Phone
        varchar DeviceFingerprint
        varchar IPAddress
        varchar Postcode
        datetime AccountCreatedAt
    }

    Address {
        int     AddressID       PK
        int     CustomerID      FK
        varchar AddressLine1
        varchar City
        varchar Postcode
        varchar Country
        varchar AddressType
    }

    Product {
        int     ProductID       PK
        varchar ProductName
        varchar Category
        decimal Price
        varchar Description
        int     StockLevel
    }

    Order {
        int     OrderID         PK
        int     CustomerID      FK
        int     AddressID       FK
        char    CardLastFour
        varchar BankRef
        varchar OrderCity
        datetime OrderDate
        decimal TotalAmount
        varchar OrderStatus
    }

    Return {
        int     ReturnID        PK
        int     OrderID         FK
        int     CustomerID      FK
        int     ProductID       FK
        datetime ReturnDate
        varchar ReturnReason
        varchar ReturnStatus
        decimal RefundAmount
    }

    Refund {
        int     RefundID        PK
        int     ReturnID        FK
        varchar BankRef
        decimal RefundAmount
        datetime RefundDate
        varchar RefundStatus
    }

    FraudAlert {
        int     FraudAlertID    PK
        int     CustomerID      FK
        int     AnalystID       FK
        varchar AlertType
        datetime DetectedAt
        decimal FraudScore
        varchar Status
        varchar Notes
    }

    Customer    ||--o{ Address     : "has"
    Customer    ||--o{ Order       : "places"
    Customer    ||--o{ Return      : "files"
    Customer    ||--o{ FraudAlert  : "flagged by"
    Analyst     ||--o{ FraudAlert  : "assigned to"
    Address     ||--o{ Order       : "ships to"
    Product     ||--o{ Return      : "returned in"
    Order       ||--o| Return      : "has"
    Return      ||--o| Refund      : "triggers"
```

## Fraud Signal Columns

| Column | Table | Fraud Pattern |
|---|---|---|
| `Phone` | Customer | Duplicate Phone |
| `DeviceFingerprint` | Customer | Suspect eCommerce / Fraud Ring |
| `IPAddress` | Customer | Suspect eCommerce |
| `Postcode` | Customer, Address | Fraud Ring geographic clustering |
| `BankRef` | Order, Refund | Fraud Ring, Skimming |
| `CardLastFour` | Order | Skimming |
| `OrderCity` | Order | Skimming (impossible travel) |
