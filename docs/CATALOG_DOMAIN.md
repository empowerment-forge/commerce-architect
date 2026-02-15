# Catalog Domain Design

## Product Model

Fields:

-   name
-   description
-   product_type
-   price
-   is_active
-   created_at

------------------------------------------------------------------------

# Design Decisions

-   product_type allows future branching logic
-   is_active supports soft deactivation
-   DecimalField ensures currency precision

------------------------------------------------------------------------

# ORM Pattern

Django ORM maps models to tables.

Migration files define schema evolution.

QuerySets provide database abstraction.
