import pandas as pd 
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
import os
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from db_sql import (
    get_postgres_engine,
    init_sqlite_db,
    load_orders_postgres,
    load_orders_sqlite,
    query_monthly_sales_by_category,
    query_top3_customers,
    load_marketing_csv,
    clean_marketing_data,
    aggregate_sales_monthly,
    merge_sales_marketing,
    compute_monthly_roi,
    check_channel_completeness,
    plot_sales_vs_spend,
    build_top3_customers,
    roi_quality_notes,
    extra_presentation_tables
)


query_category = """
WITH orders_by_month AS (
    SELECT 
        TO_CHAR(order_date, 'YYYY-MM') AS month, 
        product_category, order_amount
    FROM orders
)
SELECT 
    month, product_category, SUM(order_amount) AS total_sales, 
    COUNT(*) AS total_orders
FROM orders_by_month
GROUP BY month, product_category
"""
query = """
WITH orders_by_month AS (
    SELECT 
        TO_CHAR(order_date, 'YYYY-MM') AS month, 
        order_amount
    FROM orders
)
SELECT 
    month, SUM(order_amount) AS total_sales, 
    COUNT(*) AS total_orders
FROM orders_by_month
GROUP BY month
"""

# для гарних графіків
sns.set(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.figsize"] = (12, 6)


def main():
    # 0) Налаштування шляхів
    csv_path = "marketing_spend.csv"  # експортований CSV з Google Sheets
    sqlite_path = "orders_sqlite.db"
    orders_sql_path = "orders.sql"
    orders_sqlite_sql_path = "orders_sqlite.sql"  # якщо створюєте через SQLite

    # 1) Варіант A: PostgreSQL (рекомендовано)
    # Рядок підключення змінних оточення
    pg_url = os.getenv("POSTGRES_URL")
    pg_engine = get_postgres_engine(pg_url)

    # 2) Альтернатива B: SQLite (локально, без сервера)
    # SQLite зручний для навчання та повторюваності
    sqlite_conn = init_sqlite_db(sqlite_path, orders_sqlite_sql_path)

    # 3) Завантаження orders з PostgreSQL або SQLite:
    orders_pg = load_orders_postgres(pg_engine)
    orders_sqlite = load_orders_sqlite(sqlite_conn)

    # 4) SQL-запити: агрегати продажів та топ-3 клієнти
    monthly_sales_cat_pg = query_monthly_sales_by_category(pg_engine)
    top3_customers_pg = query_top3_customers(pg_engine)

    # 5) Завантаження та чистка маркетингових даних
    marketing_raw = load_marketing_csv(csv_path)
    marketing_clean = clean_marketing_data(marketing_raw)

    # 6) Агрегати продажів і об’єднання з маркетингом
    monthly_sales = aggregate_sales_monthly(orders_pg)  # або orders_sqlite
    sales_marketing = merge_sales_marketing(monthly_sales, marketing_clean)

    # 7) ROI по місяцях
    monthly_roi = compute_monthly_roi(sales_marketing)

    # 8) Перевірка повноти по каналах
    channel_check = check_channel_completeness(marketing_clean)

    # 9) Графіки: Продажі vs Витрати
    plot_sales_vs_spend(sales_marketing, marketing_clean)

    # 10) Топ-3 клієнти за витратами
    top3_customers = build_top3_customers(orders_pg)

    # 11) ROI-таблиці та зауваження до якості даних
    notes = roi_quality_notes(marketing_clean)

    # 12) Додаткові корисні таблиці для презентації
    tables = extra_presentation_tables(sales_marketing, marketing_clean)

    # 13) Збережіть ключові результати у CSV/MD або виведіть у консоль
    monthly_sales.to_csv("out_monthly_sales.csv", index=False)
    sales_marketing.to_csv("out_sales_marketing.csv", index=False)
    monthly_roi.to_csv("out_monthly_roi.csv", index=False)
    top3_customers.to_csv("out_top3_customers.csv", index=False)
    channel_check.to_csv("out_channel_check.csv", index=False)

    print("Короткі зауваження до якості даних:")
    for n in notes:
        print("-", n)

if __name__ == "__main__":
    main()