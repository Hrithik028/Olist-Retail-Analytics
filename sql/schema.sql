-- Primary keys for the Gold dimensions
ALTER TABLE gold.dim_customer
ADD CONSTRAINT pk_dim_customer
PRIMARY KEY (customer_id);

ALTER TABLE gold.dim_product
ADD CONSTRAINT pk_dim_product
PRIMARY KEY (product_id);

ALTER TABLE gold.dim_seller
ADD CONSTRAINT pk_dim_seller
PRIMARY KEY (seller_id);

ALTER TABLE gold.dim_date
ADD CONSTRAINT pk_dim_date
PRIMARY KEY (date_key);

-- The fact-table grain is one row per order item.
ALTER TABLE gold.fact_sales
ADD CONSTRAINT pk_fact_sales
PRIMARY KEY (order_id, order_item_id);

-- Foreign keys
ALTER TABLE gold.fact_sales
ADD CONSTRAINT fk_fact_customer
FOREIGN KEY (customer_id)
REFERENCES gold.dim_customer(customer_id);

ALTER TABLE gold.fact_sales
ADD CONSTRAINT fk_fact_product
FOREIGN KEY (product_id)
REFERENCES gold.dim_product(product_id);

ALTER TABLE gold.fact_sales
ADD CONSTRAINT fk_fact_seller
FOREIGN KEY (seller_id)
REFERENCES gold.dim_seller(seller_id);

ALTER TABLE gold.fact_sales
ADD CONSTRAINT fk_fact_date
FOREIGN KEY (date_key)
REFERENCES gold.dim_date(date_key);
