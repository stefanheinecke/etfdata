from prefect import task, flow
from prefect.server.schemas.schedules import CronSchedule
import pandas as pd

# Extraction
@task
def extract():
    df = pd.read_csv("sales.csv", sep=";")
    return df

# Transformation
@task
def transform(df):
    df.dropna(inplace=True)
    df["quantity"] = df["quantity"].astype(int)
    return df

# Loading

def load(df):
    df.to_csv("cleaned.csv", index=False)

@flow(
    name="etl_flow",
    schedule=CronSchedule(cron="*/10 * * * *")
)
def pipeline():
    df = extract()
    df = transform(df)
    load(df)

if __name__ == "__main__":
    pipeline()