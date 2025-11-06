-- Star Schema for Retail Data Warehouse

-- Dimension Table: Date
drop table if exists dim_date cascade;
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    sale_date DATE,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    month_name TEXT,
    quarter INTEGER
);

-- Dimension Table: Product
drop table if exists dim_product cascade;
CREATE TABLE dim_product (
    product_id SERIAL PRIMARY KEY,
    product_name TEXT UNIQUE,
    category TEXT
);

-- Dimension Table: Region
drop table if exists dim_region cascade;
CREATE TABLE dim_region (
    region_id SERIAL PRIMARY KEY,
    region_name TEXT UNIQUE
);

-- Dimension Table: Customer
drop table if exists dim_customer cascade;
CREATE TABLE dim_customer (
    customer_id SERIAL PRIMARY KEY,
    customer_name TEXT UNIQUE,
    segment TEXT
);

-- Fact Table: Sales
drop table if exists fact_sales cascade;
CREATE TABLE fact_sales (
    sale_id BIGSERIAL PRIMARY KEY,
    date_key INTEGER REFERENCES dim_date(date_key),
    product_id INTEGER REFERENCES dim_product(product_id),
    region_id INTEGER REFERENCES dim_region(region_id),
    customer_id INTEGER REFERENCES dim_customer(customer_id),
    quantity INTEGER,
    unit_price NUMERIC,
    amount NUMERIC
);
