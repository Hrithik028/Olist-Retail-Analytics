# Dataset setup

This project uses the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The complete dataset is not stored in this repository.

Download the dataset from Kaggle and place these files in `data/raw/`:

```text
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_orders_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

Running `python src/bronze.py` creates source-preserving copies with ingestion metadata in `data/bronze/`. Both local data directories are excluded by `.gitignore`.

Dataset rights remain with the original dataset provider. The repository's MIT License applies only to the project source code and documentation.
