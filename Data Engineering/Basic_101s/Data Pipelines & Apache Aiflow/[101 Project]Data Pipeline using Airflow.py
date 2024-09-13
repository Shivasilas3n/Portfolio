from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import requests
import pandas as pd
import boto3
import os

# Airflow DAG configuration
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'weather_etl_dag',
    default_args=default_args,
    description='ETL DAG for Weather API',
    schedule_interval=timedelta(days=1),
)

# Fetch weather data from the API
def fetch_weather_data(**kwargs):
    API_KEY = 'ded921feda6df26b8d6f22fd9253c883'
    CITY = 'Dublin'
    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}"
    response = requests.get(url)
    weather_data = response.json()
    return weather_data

# Process weather data
def process_weather_data(**kwargs):
    ti = kwargs['ti']
    weather_data = ti.xcom_pull(task_ids='fetch_weather_data')
    processed_data = {
        'city': weather_data['name'],
        'temperature': weather_data['main']['temp'],
        'humidity': weather_data['main']['humidity'],
        'description': weather_data['weather'][0]['description'],
        'date': pd.Timestamp.now()
    }
    return processed_data

# Store data in S3
def store_data_in_s3(**kwargs):
    ti = kwargs['ti']
    processed_data = ti.xcom_pull(task_ids='process_weather_data')

    # Convert to a DataFrame
    df = pd.DataFrame([processed_data])

    # Save to CSV
    filename = '/tmp/weather_data.csv'
    df.to_csv(filename, index=False)

    # Upload to S3
    s3 = boto3.client('s3')
    bucket_name = 'your_s3_bucket_name'
    s3_file_name = f'weather_data_{datetime.now().strftime("%Y_%m_%d")}.csv'

    s3.upload_file(filename, bucket_name, s3_file_name)

    # Clean up
    os.remove(filename)

# Define tasks
fetch_weather = PythonOperator(
    task_id='fetch_weather_data',
    python_callable=fetch_weather_data,
    provide_context=True,
    dag=dag,
)

process_weather = PythonOperator(
    task_id='process_weather_data',
    python_callable=process_weather_data,
    provide_context=True,
    dag=dag,
)

store_weather = PythonOperator(
    task_id='store_data_in_s3',
    python_callable=store_data_in_s3,
    provide_context=True,
    dag=dag,
)

# Set task dependencies
fetch_weather >> process_weather >> store_weather
