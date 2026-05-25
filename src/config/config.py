from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    R2_ENDPOINT_URL: str = "http://fake_url"
    R2_ACCESS_KEY: str = "fake_key"
    R2_SECRET_KEY: str = "fake_secret_key"
    R2_BUCKET_NAME: str = "fake_bucket_name"

    RESEND_API_KEY: str = ""                                   
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"           


    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1" 
    
    MLFLOW_TRACKING_URI: str = "http://mlflow:5000"
    MLFLOW_EXPERIMENT_NAME: str = "orcaml-experiments"

    CACHE_TTL_DAYS: int = 7
    CACHE_MAX_SIZE_GB: int = 10
    CACHE_MAX_MODELS: int = 20
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()