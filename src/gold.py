"""Build the reporting-ready Gold star schema from PostgreSQL Silver tables."""

import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text


load_dotenv()


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "olist"),
    )


def main() -> None:
    engine = create_engine(database_url())

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))

    customers = pd.read_sql("SELECT * FROM silver.customers", engine)
    orders = pd.read_sql("SELECT * FROM silver.orders", engine)
    items = pd.read_sql("SELECT * FROM silver.order_items", engine)
    products = pd.read_sql("SELECT * FROM silver.products", engine)
    sellers = pd.read_sql("SELECT * FROM silver.sellers", engine)

    dim_customer = customers[
        ["customer_id", "customer_unique_id", "customer_city", "customer_state"]
    ].drop_duplicates()

    dim_product = products[
        [
            "product_id",
            "product_category_name",
            "product_category_name_english",
            "product_weight_g",
        ]
    ].drop_duplicates()

    dim_seller = sellers[
        ["seller_id", "seller_city", "seller_state"]
    ].drop_duplicates()

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"]
    )
    orders["order_delivered_customer_date"] = pd.to_datetime(
        orders["order_delivered_customer_date"], errors="coerce"
    )

    dates = orders["order_purchase_timestamp"].dt.date.drop_duplicates()
    dim_date = pd.DataFrame({"full_date": pd.to_datetime(dates)})
    dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["day"] = dim_date["full_date"].dt.day
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["month_name"] = dim_date["full_date"].dt.month_name()
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["year"] = dim_date["full_date"].dt.year

    fact_sales = items[
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "price",
            "freight_value",
        ]
    ].merge(
        orders[
            [
                "order_id",
                "customer_id",
                "order_status",
                "order_purchase_timestamp",
                "order_delivered_customer_date",
            ]
        ],
        on="order_id",
        how="left",
    )

    fact_sales["date_key"] = (
        fact_sales["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int)
    )
    fact_sales["item_total"] = fact_sales["price"] + fact_sales["freight_value"]
    fact_sales["delivery_days"] = (
        fact_sales["order_delivered_customer_date"]
        - fact_sales["order_purchase_timestamp"]
    ).dt.days
    fact_sales = fact_sales[
        [
            "order_id",
            "order_item_id",
            "customer_id",
            "product_id",
            "seller_id",
            "date_key",
            "price",
            "freight_value",
            "item_total",
            "order_status",
            "delivery_days",
        ]
    ]

    print(f"dim_date: {len(dim_date):,}")
    print(f"fact_sales: {len(fact_sales):,}")
    print(
        "Unique fact key:",
        not fact_sales.duplicated(["order_id", "order_item_id"]).any(),
    )

    relationship_checks = {
        "Customer FK issues": ~fact_sales["customer_id"].isin(dim_customer["customer_id"]),
        "Product FK issues": ~fact_sales["product_id"].isin(dim_product["product_id"]),
        "Seller FK issues": ~fact_sales["seller_id"].isin(dim_seller["seller_id"]),
        "Date FK issues": ~fact_sales["date_key"].isin(dim_date["date_key"]),
    }
    for label, invalid_mask in relationship_checks.items():
        print(f"{label}: {invalid_mask.sum()}")

    gold_tables = {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_seller": dim_seller,
        "dim_date": dim_date,
        "fact_sales": fact_sales,
    }
    for name, dataframe in gold_tables.items():
        dataframe.to_sql(
            name,
            engine,
            schema="gold",
            if_exists="replace",
            index=False,
            chunksize=5000,
        )
        print(f"Loaded gold.{name}")


if __name__ == "__main__":
    main()
