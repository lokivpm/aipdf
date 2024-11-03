#config.py
from dotenv import load_dotenv
import os
import boto3
load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL")

REDIS_URL = os.getenv("REDIS_URL")

#Smtp
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
#OpenAi
openai_api_key = os.getenv('OPENAI_API_KEY')
#S3
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")


s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

class S3DocumentLoader:
    def __init__(self, bucket_name):
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name

    def load(self, file_key):
        obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
        return obj['Body'].read() 

