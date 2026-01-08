import pandas as pd 
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

engine = create_engine('postgresql://postgres:2625217@localhost:5432/postgres')

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


#  EDA
# print(df.info())
# print(f"Розмір таблиці: {df.shape}")
# print("Пропуски по колонках:")
# print(df.isna().sum())
# print(f"Кількість дублікатів: {df.duplicated().sum()}")
# print(df.describe())
# print(df.describe(include='object'))
# print(df.nunique())

# Clean Database
df = clean_marketing_data(load_marketing_csv(csv_path))
# print(df)


# df = df.drop_duplicates()
# df = df.dropna(subset=['channel', 'spend_amount'])
# df['spend_amount'] = pd.to_numeric(df['spend_amount'], errors='coerce')
# # print(df['spend_amount'].isna().sum(), "рядків мають некоректні символи")
# df = df[df['spend_amount'] >= 0]
# # print(df.shape)
# # print(df)

# df['channel'] = df['channel'].str.lower().str.strip()
# df = df.groupby(['month', 'channel'], as_index=False)['spend_amount'].sum()
# df['month'] = pd.to_datetime(df['month'])
# pivot_df = df.pivot(index='month', columns='channel', values='spend_amount')
# # print("Пропущено записів за місяцями:")
# # print(pivot_df.isna().sum())




# Завантажуємо в DataFrame
df_orders = pd.read_sql(query, engine)

# print(df_orders)
# print(df)

df_orders['month'] = pd.to_datetime(df_orders['month'], utc=True).dt.tz_localize(None).dt.normalize()
df['month'] = pd.to_datetime(df['month'], utc=True).dt.tz_localize(None).dt.normalize()
df_merged = pd.merge(df, df_orders, on='month', how='left')
# print(df_merged)
# print(df_merged['total_sales'].max(), df_merged['spend_amount'].max())

df_plot = df_merged.copy().sort_values('month') 
df_plot['month_str'] = df_plot['month'].dt.strftime('%Y-%m-%d')

max_val = max(df_plot['total_sales'].max(), df_plot['spend_amount'].max())

upper_limit = max_val * 1.15
fig, ax1 = plt.subplots(figsize=(14, 7))

sns.barplot(data=df_plot, x='month_str', y='total_sales', ax=ax1, color='skyblue', alpha=0.4, label='Total Sales', errorbar=None) 
ax2 = ax1.twinx() 
sns.lineplot(data=df_plot, x='month_str', y='spend_amount', hue='channel', marker='o', ax=ax2)
ax1.set_ylim(0, upper_limit) 
ax2.set_ylim(0, upper_limit)

ax2.legend(loc='upper left', bbox_to_anchor=(1, 1))

ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45) 
plt.title('Sales vs Marketing Spend (Correct 1:1 Scale)') 
plt.tight_layout() 
plt.show()