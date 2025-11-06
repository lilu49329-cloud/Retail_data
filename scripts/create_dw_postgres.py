
#!/usr/bin/env python3
"""create_dw_postgres.py
- Connects to PostgreSQL, creates database (if not exists), creates star schema tables,
  and loads data from data/train.csv into the data warehouse.
Usage:
    python create_dw_postgres.py --config docs/config_template.json
Environment variables (take precedence):
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB
"""
import os
import argparse
import json
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# -------------------- Helpers --------------------
def load_config(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding='utf-8'))
    return {}

def env_or_config(config):
    return {
        "host": os.getenv("PG_HOST", config.get("host", "localhost")),
        "port": int(os.getenv("PG_PORT", config.get("port", 5432))),
        "user": os.getenv("PG_USER", config.get("user", "postgres")),
        "password": os.getenv("PG_PASSWORD", config.get("password", "postgres")),
        "database": os.getenv("PG_DB", config.get("database", "retail_dw"))
    }

# -------------------- Main --------------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="Path to JSON config", default="docs/config_template.json")
    args = p.parse_args()

    cfg = load_config(args.config)
    c = env_or_config(cfg)

    print("Using connection:", {k: v for k, v in c.items() if k != 'password'})

    # 1) Ensure target database exists. Connect to default 'postgres' DB to create if needed.
    create_db_conn = psycopg2.connect(host=c['host'], port=c['port'], user=c['user'], password=c['password'], dbname='postgres')
    create_db_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = create_db_conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (c['database'],))
    exists = cur.fetchone()
    if not exists:
        print("Database not found. Creating database", c['database'])
        cur.execute("CREATE DATABASE " + c['database'])
    else:
        print("Database exists:", c['database'])
    cur.close()
    create_db_conn.close()

    # 2) Connect to the target database via SQLAlchemy for easy to_sql
    engine_url = f"postgresql+psycopg2://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['database']}"
    engine = create_engine(engine_url)

    # 3) Read CSV
    data_path = Path("data/train.csv")
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found at {data_path}")
    df = pd.read_csv(data_path)
    print("Read rows:", len(df), "columns:", list(df.columns))

    # 4) Simple heuristic mapping (adjust if your CSV has different column names)
    # We expect at least: Order Date / Ship Date, Product ID or Product Name, Sales, Region
    # Convert dates and create standardized columns for the DW.
    date_col = None
    for c in df.columns:
        if 'date' in c.lower():
            date_col = c
            break
    if date_col is None:
        raise ValueError("No date-like column found in CSV")

    # pick product column (Product ID or Product Name)
    product_col = None
    for c in df.columns:
        if 'product' in c.lower():
            product_col = c
            break
    if product_col is None:
        product_col = df.columns[0]

    # pick price/sales column
    price_col = None
    for c in df.columns:
        if 'sale' in c.lower() or 'price' in c.lower() or 'amount' in c.lower():
            price_col = c
            break
    if price_col is None:
        price_col = df.columns[-1]

    # region/location
    region_col = None
    for c in df.columns:
        if any(k in c.lower() for k in ['region','state','city','location']):
            region_col = c
            break
    if region_col is None:
        region_col = df.columns[0]

    # customer
    customer_col = None
    for c in df.columns:
        if any(k in c.lower() for k in ['customer','buyer','client','user']):
            customer_col = c
            break
    # Nếu không có cột khách hàng, tạo dữ liệu giả
    if customer_col is None:
        df['customer'] = 'Unknown_Customer'
    else:
        df['customer'] = df[customer_col].astype(str)

    # normalize
    df['sale_date'] = pd.to_datetime(df[date_col], errors='coerce')
    df['product'] = df[product_col].astype(str)
    df['unit_price'] = pd.to_numeric(df[price_col], errors='coerce').fillna(0.0)
    # assume quantity not provided -> set to 1 per record
    df['quantity'] = 1
    df['region'] = df[region_col].astype(str)
    df['amount'] = df['quantity'] * df['unit_price']
    df['customer'] = df['customer'].astype(str)

    # Bước tạo bảng đã được tách ra file scripts/star_schema.sql. Đảm bảo đã chạy file SQL này trước khi nạp dữ liệu.

    # 6) Populate dim tables and fact table
    # dim_date
    dates = pd.DataFrame({'sale_date': pd.to_datetime(df['sale_date'].dt.date.unique())})
    # Loại bỏ các giá trị thiếu (NaT)
    dates = dates.dropna(subset=['sale_date'])
    # Nếu vẫn còn thiếu, điền giá trị mặc định là ngày đầu tiên trong tập dữ liệu
    if dates['sale_date'].isnull().any():
        default_date = pd.to_datetime(df['sale_date'].dropna().iloc[0])
        dates['sale_date'] = dates['sale_date'].fillna(default_date)
    dates['year'] = dates['sale_date'].dt.year
    dates['month'] = dates['sale_date'].dt.month
    dates['day'] = dates['sale_date'].dt.day
    dates['month_name'] = dates['sale_date'].dt.strftime('%B')
    dates['quarter'] = dates['sale_date'].dt.quarter
    dates['date_key'] = dates['sale_date'].dt.strftime('%Y%m%d').astype(int)
    dates = dates[['date_key','sale_date','year','month','day','month_name','quarter']]
    dates.to_sql('dim_date', engine, if_exists='append', index=False, method='multi')

    # dim_product, dim_region, dim_customer - unique lists
    prods = pd.DataFrame({
        'product_name': df['product'].astype(str).str.strip().replace('', 'Unknown_Product'),
        'category': df['Category'].astype(str).str.strip().replace('', 'Unknown_Category')
    }).drop_duplicates()
    regs = pd.DataFrame({'region_name': df['region'].astype(str).str.strip().replace('', 'Unknown')}).drop_duplicates()
    custs = pd.DataFrame({
        'customer_name': df['customer'].astype(str).str.strip().replace('', 'Unknown_Customer'),
        'segment': df['Segment'].astype(str).str.strip().replace('', 'Unknown_Segment')
    }).drop_duplicates()
    prods.to_sql('dim_product', engine, if_exists='append', index=False, method='multi')
    regs.to_sql('dim_region', engine, if_exists='append', index=False, method='multi')
    custs.to_sql('dim_customer', engine, if_exists='append', index=False, method='multi')

    # build maps
    prod_map = {}
    reg_map = {}
    cust_map = {}
    with engine.connect() as conn:
        res = conn.execute(text("SELECT product_id, product_name FROM dim_product"))
        for row in res:
            prod_map[row[1]] = row[0]
        res = conn.execute(text("SELECT region_id, region_name FROM dim_region"))
        for row in res:
            reg_map[row[1]] = row[0]
        res = conn.execute(text("SELECT customer_id, customer_name FROM dim_customer"))
        for row in res:
            cust_map[row[1]] = row[0]

    # Prepare fact rows for insert
    fact_rows = []
    # Lấy giá trị ngày mặc định là ngày đầu tiên không bị thiếu
    default_date = pd.to_datetime(df['sale_date'].dropna().iloc[0])
    for _, r in df.iterrows():
        sale_date = r['sale_date']
        if pd.isnull(sale_date) or str(sale_date) == 'NaT':
            sale_date = default_date
        date_key = int(sale_date.strftime('%Y%m%d'))
        pname = str(r['product']).strip()
        rname = str(r['region']).strip()
        cname = str(r['customer']).strip()
        pid = prod_map.get(pname)
        rid = reg_map.get(rname)
        cid = cust_map.get(cname)
        if pid is None:
            with engine.connect() as conn:
                res = conn.execute(text("INSERT INTO dim_product(product_name) VALUES (:pname) RETURNING product_id"), {"pname": pname})
                pid = res.fetchone()[0]
                prod_map[pname] = pid
        if rid is None:
            with engine.connect() as conn:
                res = conn.execute(text("INSERT INTO dim_region(region_name) VALUES (:rname) RETURNING region_id"), {"rname": rname})
                rid = res.fetchone()[0]
                reg_map[rname] = rid
        if cid is None:
            with engine.connect() as conn:
                res = conn.execute(text("INSERT INTO dim_customer(customer_name) VALUES (:cname) RETURNING customer_id"), {"cname": cname})
                cid = res.fetchone()[0]
                cust_map[cname] = cid
        fact_rows.append({
            "date_key": date_key,
            "product_id": pid,
            "region_id": rid,
            "customer_id": cid,
            "quantity": int(r['quantity']),
            "unit_price": float(r['unit_price']),
            "amount": float(r['amount'])
        })

    # bulk insert facts using DataFrame.to_sql on a temporary table then INSERT ... SELECT
    facts_df = pd.DataFrame(fact_rows)
    facts_df.to_sql('fact_sales_temp', engine, if_exists='replace', index=False, method='multi')
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO fact_sales(date_key, product_id, region_id, customer_id, quantity, unit_price, amount)
            SELECT date_key, product_id, region_id, customer_id, quantity, unit_price, amount FROM fact_sales_temp
        """))
        conn.execute(text("DROP TABLE IF EXISTS fact_sales_temp"))

    print("Data warehouse creation & load complete.")

if __name__ == "__main__":
    main()
