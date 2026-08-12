-- 1. Aggregation: total sales value by product category
SELECT
    COALESCE(p.product_category_name_english, 'unknown') AS category,
    ROUND(SUM(f.price)::numeric, 2) AS sales_value
FROM gold.fact_sales AS f
JOIN gold.dim_product AS p
    ON f.product_id = p.product_id
GROUP BY COALESCE(p.product_category_name_english, 'unknown')
ORDER BY sales_value DESC;

-- 2. Window function: rank product categories by sales value
WITH category_sales AS (
    SELECT
        COALESCE(p.product_category_name_english, 'unknown') AS category,
        SUM(f.price) AS sales_value
    FROM gold.fact_sales AS f
    JOIN gold.dim_product AS p
        ON f.product_id = p.product_id
    GROUP BY COALESCE(p.product_category_name_english, 'unknown')
)
SELECT
    category,
    ROUND(sales_value::numeric, 2) AS sales_value,
    RANK() OVER (
        ORDER BY sales_value DESC
    ) AS sales_rank
FROM category_sales
ORDER BY sales_rank;

-- 3. Star-schema join: category sales over time
SELECT
    d.year,
    COALESCE(p.product_category_name_english, 'unknown') AS category,
    ROUND(SUM(f.price)::numeric, 2) AS sales_value
FROM gold.fact_sales AS f
JOIN gold.dim_product AS p
    ON f.product_id = p.product_id
JOIN gold.dim_date AS d
    ON f.date_key = d.date_key
GROUP BY d.year, COALESCE(p.product_category_name_english, 'unknown')
ORDER BY d.year, sales_value DESC;

-- 4. Index and query-plan analysis
EXPLAIN ANALYZE
SELECT *
FROM gold.fact_sales
WHERE date_key = 20171124;

CREATE INDEX IF NOT EXISTS idx_fact_sales_date_key
ON gold.fact_sales(date_key);

EXPLAIN ANALYZE
SELECT *
FROM gold.fact_sales
WHERE date_key = 20171124;

-- The original tested plan used a Bitmap Index Scan after index creation.

-- 5. Data-quality check
SELECT
    COUNT(*) AS invalid_sales_rows
FROM gold.fact_sales
WHERE price < 0
   OR freight_value < 0
   OR delivery_days < 0;

-- Result from the completed project run: invalid_sales_rows = 0.
