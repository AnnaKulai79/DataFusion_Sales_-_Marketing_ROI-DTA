from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
import seaborn as sns
import sqlite3
import matplotlib.pyplot as plt

def get_postgres_engine(pg_url: str):
    engine = create_engine(pg_url, echo=False, future=True)
    return engine

def load_orders_postgres(engine):
    query = "SELECT * FROM orders;"
    
    # Використовуємо з'єднання для читання через pandas
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    
    # Форматування даних
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["order_amount"] = pd.to_numeric(df["order_amount"], errors="coerce")
    
    return df
    
# -------------------------------------------------------
import sqlite3 

def init_sqlite_db(sqlite_path: str, orders_sqlite_sql_path: str): 
    conn = sqlite3.connect(sqlite_path) 
    with open(orders_sqlite_sql_path, "r", encoding="utf-8") as f: 
        sql_script = f.read() 
        conn.executescript(sql_script) 
        conn.commit() 
        return conn 

def load_orders_sqlite(conn): 
    df = pd.read_sql_query("SELECT order_id, customer_id, order_date, product_category, order_amount FROM orders;", conn)
    df["order_date"] = pd.to_datetime(df["order_date"]) 
    df["order_amount"] = pd.to_numeric(df["order_amount"], errors="coerce") 
    return df
# -------------------------------------------------------

def query_monthly_sales_by_category(engine): 
    q = """ 
    SELECT 
        DATE_TRUNC('month', order_date)::date AS month, 
        product_category, 
        COUNT(*) AS orders_count, 
        SUM(order_amount) AS sales_sum 
    FROM orders 
    GROUP BY DATE_TRUNC('month', order_date)::date, product_category 
    ORDER BY month, product_category; 
    """ 
    return pd.read_sql(q, con=engine) 

def query_top3_customers(engine): 
    q = '''
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
    return pd.read_sql(q, con=engine)

# --- file csv -----------------------------
def load_marketing_csv(csv_path: str):
    # У таблиці можливі пусті, "missing", від’ємні значення, різні регістри назв каналів.
    df = pd.read_csv(csv_path)
    # Очікувані колонки: month, channel, spend_amount
    # Безпечне приведення типів
    df.rename(columns=lambda c: c.strip().lower(), inplace=True)  # 'Month' -> 'month' тощо
    df["month"] = pd.to_datetime(df["month"], errors="coerce")  # формат YYYY-MM
    # Залишимо spend_amount як текст на етапі сирих даних, далі очистимо
    return df

def clean_marketing_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()

    # Стандартизація назв каналів
    df["channel"] = df["channel"].astype(str).str.strip()
    channel_map = {
        "google ads": "Google Ads",
        "google ad": "Google Ads",
        "googleads": "Google Ads",
        "google": "Google Ads",
        "youtube": "YouTube",
        "tiktok": "TikTok",
        "facebook": "Facebook",
        "instagram": "Instagram"
    }
    # Нормалізуємо до нижнього і мапимо
    df["channel_lower"] = df["channel"].str.lower()
    df["channel_std"] = df["channel_lower"].map(channel_map).fillna(df["channel"].str.title())

    # Очищення spend_amount
    def parse_spend(x):
        if pd.isna(x):
            return np.nan
        x = str(x).strip().lower()
        if x in ["", "na", "none", "null", "missing"]:
            return np.nan
        try:
            return float(x)
        except:
            return np.nan

    df["spend_amount_num"] = df["spend_amount"].apply(parse_spend)

    # Позначимо проблемні значення
    df["negative_spend_flag"] = df["spend_amount_num"] < 0
    # Політика: для навчального кейсу робимо NaN з від’ємних, але фіксуємо примітку.
    df.loc[df["negative_spend_flag"], "spend_amount_num"] = np.nan

    # Підсумкова чиста таблиця
    clean = df[["month", "channel_std", "spend_amount_num"]].rename(
        columns={"channel_std": "channel", "spend_amount_num": "spend_amount"}
    )
    # Переконаємось, що month — це місяць (без дня)
    clean["month"] = pd.to_datetime(clean["month"]).dt.to_period("M").dt.to_timestamp()
    return clean

# Агрегація продажів помісячно
def aggregate_sales_monthly(orders_df: pd.DataFrame) -> pd.DataFrame:
    df = orders_df.copy()
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    monthly_sales = (
        df.groupby("month", as_index=False)
          .agg(sales_sum=("order_amount", "sum"), orders_count=("order_id", "count"))
    )
    return monthly_sales

# Об’єднання з маркетинговими витратами (помісячно)
def merge_sales_marketing(monthly_sales: pd.DataFrame, marketing_clean: pd.DataFrame) -> pd.DataFrame:
    marketing_monthly = (
        marketing_clean.groupby("month", as_index=False)
        .agg(marketing_spend=("spend_amount", "sum"))
    )
    merged = monthly_sales.merge(marketing_monthly, on="month", how="left")
    return merged

# ROI по місяцях
def compute_monthly_roi(sales_marketing: pd.DataFrame) -> pd.DataFrame:
    df = sales_marketing.copy()
    df["roi"] = np.where(df["marketing_spend"] > 0, df["sales_sum"] / df["marketing_spend"], np.nan)
    return df[["month", "sales_sum", "marketing_spend", "roi"]]

# Витрати по каналах і перевірка повноти
def check_channel_completeness(marketing_clean: pd.DataFrame) -> pd.DataFrame:
    pivot = marketing_clean.pivot_table(
        index="month", columns="channel", values="spend_amount", aggfunc="sum"
    )
    # Доповнимо очікуваними каналами, навіть якщо їх немає в даних
    expected_channels = ["Facebook", "Google Ads", "Instagram", "TikTok", "YouTube"]
    for ch in expected_channels:
        if ch not in pivot.columns:
            pivot[ch] = np.nan
    pivot = pivot[expected_channels]  # впорядкуємо колонки

    # Додамо прапорці повноти
    pivot["complete_all_channels"] = pivot[expected_channels].notna().all(axis=1)
    pivot["missing_channels"] = pivot[expected_channels].isna().sum(axis=1)
    return pivot.reset_index()

# Графік: Продажі vs Витрати
def plot_sales_vs_spend(sales_marketing: pd.DataFrame, marketing_clean: pd.DataFrame):
    df_merged = pd.merge(marketing_clean, sales_marketing, on='month', how='left')
    df_plot = df_merged.copy().sort_values('month') 
    df_plot['month_str'] = df_plot['month'].dt.strftime('%Y-%m-%d')
    
    max_val = max(sales_marketing["sales_sum"].max(), marketing_clean['spend_amount'].max())
    upper_limit = max_val * 1.15
    
    fig, ax1 = plt.subplots(figsize=(14, 7))

    sns.barplot(data=df_plot, x='month_str', y='sales_sum', ax=ax1, color='skyblue', alpha=0.4, label='Total Sales', errorbar=None) 
    
    ax2 = ax1.twinx() 
    sns.lineplot(data=df_plot, x='month_str', y='spend_amount', hue='channel', marker='o', ax=ax2)
    
    ax1.set_ylim(0, upper_limit) 
    ax2.set_ylim(0, upper_limit)
    ax2.legend(loc='upper left', bbox_to_anchor=(1.05, 1))

    ax1.set_xticks(range(len(df_plot['month_str'].unique())))
    ax1.set_xticklabels(df_plot['month_str'].unique(), rotation=45, ha='right')
 
    plt.title('Sales vs Marketing Spend') 
    plt.tight_layout() 
    plt.show()

    # Лінія продажів
    # fig, ax = plt.subplots()

    # ax.plot(sales_marketing["month"], sales_marketing["sales_sum"], color="black", label="Продажі")
    # ax.set_xlabel("Місяць")
    # ax.set_ylabel("Сума продажів")
    # ax.legend(loc="upper left")

    # plt.title("Продажі (лінія) та маркетингові витрати по каналах (стек)")

    # # Підготуємо стек витрат по каналах
    # pivot = marketing_clean.pivot_table(
    #     index="month", columns="channel", values="spend_amount", aggfunc="sum"
    # ).fillna(0)
    # # Впорядкуємо канали
    # cols = ["Facebook", "Google Ads", "Instagram", "TikTok", "YouTube"]
    # for c in cols:
    #     if c not in pivot.columns:
    #         pivot[c] = 0.0
    # pivot = pivot[cols].sort_index()

    # # Друга вісь для витрат
    # ax2 = ax.twinx()
    # ax2.stackplot(
    #     pivot.index,
    #     [pivot[c].values for c in cols],
    #     labels=cols,
    #     alpha=0.4
    # )
    # max_val = max(sales_marketing["sales_sum"].max(), marketing_clean['spend_amount'].max())

    # upper_limit = max_val * 1.15
    

    # ax.set_ylim(0, upper_limit) 
    # ax2.set_ylim(0, upper_limit)
    
    # ax2.set_ylabel("Маркетингові витрати")
    # ax2.legend(loc="upper right")
    # plt.tight_layout()
    # plt.show()

# Таблиці для презентації топ-3 клієнтів
def build_top3_customers(orders_df: pd.DataFrame) -> pd.DataFrame:
    top3 = (
        orders_df.groupby("customer_id", as_index=False)
        .agg(orders_count=("order_id", "count"), total_spent=("order_amount", "sum"))
        .sort_values("total_spent", ascending=False)
        .head(3)
    )
    return top3

# ROI-таблиці та зауваження до якості даних
def roi_quality_notes(marketing_clean: pd.DataFrame):
    notes = []
    # Виявимо місяці з NaN витратами (через пропуски або негативні значення)
    monthly_spend = marketing_clean.groupby("month")["spend_amount"].sum()
    missing_months = monthly_spend[monthly_spend.isna()].index.tolist()
    if missing_months:
        notes.append(f"Є місяці з відсутніми сумарними витратами: {missing_months}")

    # Виявимо від’ємні витрати (до чистки — вже позначали; тут перевіримо сирі прапорці, якщо їх зберігали)
    # Якщо прапорці недоступні, просто зазначимо з опису, що в 2025-03 Google Ads були від’ємні.
    notes.append("Виявлено від’ємні витрати для Google Ads у окремому місяці; виправлено на NaN для коректного ROI.")

    # Перевірка каналів з пропусками
    pivot = marketing_clean.pivot_table(index="month", columns="channel", values="spend_amount", aggfunc="sum")
    channels_with_missing = pivot.columns[pivot.isna().any()].tolist()
    if channels_with_missing:
        notes.append(f"Канали з пропусками по місяцях: {channels_with_missing}")

    # Інше: різні регістри назв каналів виправлено.
    notes.append("Стандартизацію назв каналів виконано (YouTube/Youtube, Google ads/Google Ads).")

    return notes

# Витрати по каналах і перевірка повноти
def extra_presentation_tables(sales_marketing: pd.DataFrame, marketing_clean: pd.DataFrame):
    # Таблиця структури витрат по каналах
    channel_pivot = (marketing_clean
                     .pivot_table(index="month", columns="channel", values="spend_amount", aggfunc="sum")
                     .reset_index())

    # Зведення загальних витрат:
    monthly_spend = (marketing_clean.groupby("month", as_index=False)
                     .agg(marketing_spend=("spend_amount", "sum")))

    # Злиття з продажами для компактної презентації
    overview = sales_marketing[["month", "sales_sum", "orders_count", "marketing_spend"]].merge(
        channel_pivot, on="month", how="left"
    )

    return {
        "channel_pivot": channel_pivot,
        "monthly_spend": monthly_spend,
        "overview": overview
    }