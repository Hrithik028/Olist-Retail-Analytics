"""Clean, validate, standardise, and load Olist data into PostgreSQL Silver."""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze"
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


def read_bronze(filename: str) -> pd.DataFrame:
    path = BRONZE_PATH / filename
    if not path.exists():
        raise FileNotFoundError(f"Bronze file not found: {path}. Run src/bronze.py first.")
    dataframe = pd.read_csv(path)
    dataframe["load_date"] = pd.to_datetime(dataframe["load_date"], errors="coerce")
    return dataframe


def main() -> None:
    bronze = {
        "customers": read_bronze("olist_customers_dataset_bronze.csv"),
        "geolocation": read_bronze("olist_geolocation_dataset_bronze.csv"),
        "orders": read_bronze("olist_orders_dataset_bronze.csv"),
        "order_items": read_bronze("olist_order_items_dataset_bronze.csv"),
        "order_payments": read_bronze("olist_order_payments_dataset_bronze.csv"),
        "order_reviews": read_bronze("olist_order_reviews_dataset_bronze.csv"),
        "products": read_bronze("olist_products_dataset_bronze.csv"),
        "sellers": read_bronze("olist_sellers_dataset_bronze.csv"),
        "product_category_translation": read_bronze(
            "product_category_name_translation_bronze.csv"
        ),
    }

    data_info = pd.DataFrame(
        {
            "dataset": bronze.keys(),
            "n_rows": [len(dataframe) for dataframe in bronze.values()],
            "n_cols": [len(dataframe.columns) for dataframe in bronze.values()],
            "null_amount": [
                dataframe.isnull().sum().sum() for dataframe in bronze.values()
            ],
        }
    )
    print(data_info.to_string(index=False))

    silver_customers = bronze["customers"].copy()
    silver_customers["customer_city"] = silver_customers["customer_city"].str.strip()
    silver_customers["customer_state"] = (
        silver_customers["customer_state"].str.strip().str.upper()
    )

    silver_sellers = bronze["sellers"].copy()
    silver_sellers["seller_city"] = silver_sellers["seller_city"].str.strip()
    silver_sellers["seller_state"] = (
        silver_sellers["seller_state"].str.strip().str.upper()
    )

    silver_translation = bronze["product_category_translation"].copy()
    silver_translation["product_category_name"] = (
        silver_translation["product_category_name"].str.strip()
    )
    silver_translation["product_category_name_english"] = (
        silver_translation["product_category_name_english"].str.strip()
    )

    silver_payments = bronze["order_payments"].copy()
    payment_key_is_unique = not silver_payments.duplicated(
        ["order_id", "payment_sequential"]
    ).any()
    print(f"Unique payment key: {payment_key_is_unique}")

    silver_order_items = bronze["order_items"].copy()
    silver_order_items["shipping_limit_date"] = pd.to_datetime(
        silver_order_items["shipping_limit_date"], errors="coerce"
    )
    item_key_is_unique = not silver_order_items.duplicated(
        ["order_id", "order_item_id"]
    ).any()
    print(f"Unique order-item key: {item_key_is_unique}")
    print(f"Negative prices: {(silver_order_items['price'] < 0).sum()}")
    print(
        "Negative freight values:",
        (silver_order_items["freight_value"] < 0).sum(),
    )

    silver_orders = bronze["orders"].copy()
    date_columns = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    silver_orders[date_columns] = silver_orders[date_columns].apply(
        pd.to_datetime, errors="coerce"
    )
    silver_orders["delivered_lifecycle_issue"] = (
        (silver_orders["order_status"] == "delivered")
        & (
            silver_orders["order_approved_at"].isnull()
            | silver_orders["order_delivered_carrier_date"].isnull()
            | silver_orders["order_delivered_customer_date"].isnull()
        )
    )
    invalid_delivery_sequence = (
        silver_orders["order_delivered_customer_date"].notna()
        & (
            silver_orders["order_delivered_customer_date"]
            < silver_orders["order_purchase_timestamp"]
        )
    )
    print(
        "Delivered orders with missing lifecycle dates:",
        silver_orders["delivered_lifecycle_issue"].sum(),
    )
    print(f"Delivery-before-purchase rows: {invalid_delivery_sequence.sum()}")

    products = bronze["products"].copy()
    products = products.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    )
    products["product_category_name"] = products["product_category_name"].str.strip()
    products = products.merge(
        silver_translation[
            ["product_category_name", "product_category_name_english"]
        ],
        on="product_category_name",
        how="left",
    )
    translation_fallback = {
        "pc_gamer": "gaming_pc",
        "portateis_cozinha_e_preparadores_de_alimentos": (
            "portable_kitchen_and_food_preparation_appliances"
        ),
    }
    products["product_category_name_english"] = products[
        "product_category_name_english"
    ].fillna(products["product_category_name"].map(translation_fallback))
    silver_products = products

    for column in [
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]:
        print(f"Negative {column}: {(silver_products[column] < 0).sum()}")
    unmatched_categories = silver_products[
        silver_products["product_category_name"].notna()
        & silver_products["product_category_name_english"].isna()
    ]
    print(
        "Categories missing translation:",
        unmatched_categories["product_category_name"].nunique(),
    )

    silver_reviews = bronze["order_reviews"].copy()
    silver_reviews[["review_creation_date", "review_answer_timestamp"]] = (
        silver_reviews[["review_creation_date", "review_answer_timestamp"]].apply(
            pd.to_datetime, errors="coerce"
        )
    )
    review_key_is_unique = not silver_reviews.duplicated(
        ["review_id", "order_id"]
    ).any()
    print(f"Unique review-order key: {review_key_is_unique}")

    silver_geolocation = bronze["geolocation"].copy()
    silver_geolocation["geolocation_city"] = (
        silver_geolocation["geolocation_city"].str.strip()
    )
    silver_geolocation["geolocation_state"] = (
        silver_geolocation["geolocation_state"].str.strip().str.upper()
    )
    geolocation_key = [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ]
    duplicate_geolocation_rows = silver_geolocation.duplicated(geolocation_key).sum()
    silver_geolocation = silver_geolocation.drop_duplicates(geolocation_key)
    invalid_coordinates = (
        ~silver_geolocation["geolocation_lat"].between(-90, 90)
        | ~silver_geolocation["geolocation_lng"].between(-180, 180)
    )
    print(f"Exact duplicate geolocation rows removed: {duplicate_geolocation_rows}")
    print(f"Invalid coordinate rows: {invalid_coordinates.sum()}")

    relationship_checks = {
        "Orders -> Customers": ~silver_orders["customer_id"].isin(
            silver_customers["customer_id"]
        ),
        "Order Items -> Orders": ~silver_order_items["order_id"].isin(
            silver_orders["order_id"]
        ),
        "Order Items -> Products": ~silver_order_items["product_id"].isin(
            silver_products["product_id"]
        ),
        "Order Items -> Sellers": ~silver_order_items["seller_id"].isin(
            silver_sellers["seller_id"]
        ),
        "Payments -> Orders": ~silver_payments["order_id"].isin(
            silver_orders["order_id"]
        ),
        "Reviews -> Orders": ~silver_reviews["order_id"].isin(
            silver_orders["order_id"]
        ),
    }
    for label, orphan_mask in relationship_checks.items():
        print(f"{label}: {orphan_mask.sum()} orphaned records")

    engine = create_engine(database_url())
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS silver"))

    silver_tables = {
        "customers": silver_customers,
        "sellers": silver_sellers,
        "orders": silver_orders,
        "order_items": silver_order_items,
        "order_payments": silver_payments,
        "order_reviews": silver_reviews,
        "products": silver_products,
        "geolocation": silver_geolocation,
        "product_category_translation": silver_translation,
    }
    for name, dataframe in silver_tables.items():
        dataframe.to_sql(
            name,
            engine,
            schema="silver",
            if_exists="replace",
            index=False,
            chunksize=5000,
        )
        print(f"Loaded silver.{name}")


if __name__ == "__main__":
    main()
