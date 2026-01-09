import pandas as pd 
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
import os
import db_sql as db
from dotenv import load_dotenv
load_dotenv()


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

query_top3 = '''
WITH orders_by_rank AS(
	SELECT customer_id, RANK() OVER(ORDER BY SUM(order_amount) DESC) AS rank_customer,
		SUM(order_amount)
	FROM orders
	GROUP BY customer_id
)

SELECT *
FROM orders_by_rank
WHERE rank_customer<=3;
'''


csv_path = 'marketing_spend.csv'

def load_marketing_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df['month'] = pd.to_datetime(df['month'], errors='coerce')
    return df

def clean_marketing_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    df['channel'] = df['channel'].astype(str).str.strip()
    channel_map = {
        "google ads": "Google Ads",
        "google ad": "Google Ads",
        "googleads": "Google Ads",
        "instagram": "Instagram",
        "tiktok": "TikTok",
        "facebook": "Facebook",
        "youtube": "YouTube"
        }
    df['channel_std'] = df['channel'].str.lower().map(channel_map).fillna(df['channel'].str.title())
    
    def parse_spend(x):
        if pd.isna(x):
            return np.nan
        x = str(x).strip().lower()
        if x in ['', 'na', 'missing', 'null', 'none']:
            return np.nan
        try:
            return float(x)
        except:
            return np.nan
    df['spend_amount_num'] = df['spend_amount'].apply(parse_spend)
    df['negativ_spend_flag'] = df['spend_amount_num'] < 0
    df.loc[df['negativ_spend_flag'], 'spend_amount_num'] = np.nan
    clean = df[['month', 'channel_std', 'spend_amount_num', 'negativ_spend_flag']].rename(columns={'channel_std': 'channel', 'spend_amount_num': 'spend_amount'})
    clean['month'] = pd.to_datetime(clean['month']).dt.to_period('M').dt.to_timestamp()
    return clean



def main():
    csv_path = "marketing_spend.csv"
    df = clean_marketing_data(load_marketing_csv(csv_path))
    print(df)
    
    orders_sql_path = "orders.sql"
    pg_url = os.getenv("POSTGRES_URL")
    pg_engine = db.get_postgres_engine(pg_url)
    orders = db.load_orders_postgres(pg_engine)
    print(orders)

if __name__ == "__main__":
    main()