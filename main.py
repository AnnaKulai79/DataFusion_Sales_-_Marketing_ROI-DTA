import pandas as pd 
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv('marketing_spend.csv')
# print(df.shape)

df = df.drop_duplicates()
df = df.dropna(subset=['channel', 'spend_amount'])
df['spend_amount'] = pd.to_numeric(df['spend_amount'], errors='coerce')

# print(df['spend_amount'].isna().sum(), "рядків мають некоректні символи")

df = df[df['spend_amount'] >= 0]


# print(df.shape)

# print(df)

df['channel'] = df['channel'].str.lower().str.strip()
df = df.groupby(['month', 'channel'], as_index=False)['spend_amount'].sum()

df['month'] = pd.to_datetime(df['month'])

pivot_df = df.pivot(index='month', columns='channel', values='spend_amount')

print("Пропущено записів за місяцями:")
print(pivot_df.isna().sum())


from sqlalchemy import create_engine

# Створюємо підключення (замініть дані на свої)
# Формат: 'postgresql://username:password@host:port/database_name'

engine = create_engine('postgresql://postgres:2625217@localhost:5432/postgres')
# Ваш SQL запит (ми додаємо YEAR, щоб не змішувати дані різних років)
query = """
WITH orders_by_month AS (
    SELECT 
        EXTRACT(YEAR FROM order_date)||'-'||EXTRACT(MONTH FROM order_date) AS month, 
        product_category, 
        order_amount
    FROM orders
)
SELECT 
    month, product_category, 
    SUM(order_amount) AS total_sales, 
    COUNT(*) AS total_orders
FROM orders_by_month
GROUP BY month, product_category
"""

# Завантажуємо в DataFrame
df_orders = pd.read_sql(query, engine)

print(df_orders)



