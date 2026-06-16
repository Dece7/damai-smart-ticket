from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Mimo (主力模型)
    mimo_api_key: str = ""
    mimo_base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    mimo_model: str = "mimo-v2.5"

    # DeepSeek (备选 + Embedding)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"

    # Embedding
    embedding_provider: str = "hash"  # hash / dashscope
    embedding_model: str = "tongyi-embedding-vision-plus"
    embedding_dimensions: int = 1024

    # DashScope (阿里云)
    dashscope_api_key: str = ""

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "3333"
    mysql_database: str = "damai_smart_ticket"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_db"

    # Reranker
    reranker_model: str = "ms-marco-TinyBERT-L-2-v2"
    reranker_top_n: int = 5
    reranker_candidate_count: int = 20

    # Java 后端 API（整合大麦票务系统）
    java_api_enabled: bool = False  # 是否启用真实 Java API
    java_api_base_url: str = "http://localhost:6085"  # Java 网关地址
    java_api_program_url: str = "http://localhost:6086"  # 节目服务地址
    java_api_order_url: str = "http://localhost:8081"  # 订单服务地址
    java_api_timeout: int = 10  # 请求超时（秒）

    # Java MySQL 直连（绕过 ES，直接查数据库）
    java_mysql_enabled: bool = False  # 是否启用 MySQL 直连
    java_mysql_host: str = "localhost"
    java_mysql_port: int = 3306
    java_mysql_user: str = "root"
    java_mysql_password: str = "3333"
    java_mysql_program_db: str = "damai_program_0"
    java_mysql_order_db: str = "damai_order_0"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
