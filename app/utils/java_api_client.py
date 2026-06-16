"""Java 后端 API 客户端

当 java_api_enabled=True 时，调用真实 Java API；
否则返回 None，工具函数回退到模拟数据。

支持两种模式：
1. HTTP API 模式：调用 Java 微服务 API
2. MySQL 直连模式：直接查询 Java 数据库（绕过 ES）
"""

import logging
import requests
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class JavaAPIClient:
    """Java 后端 API 客户端"""

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.java_api_enabled
        self.base_url = settings.java_api_base_url.rstrip("/")
        self.program_url = settings.java_api_program_url.rstrip("/")
        self.order_url = settings.java_api_order_url.rstrip("/")
        self.timeout = settings.java_api_timeout
        self._token = None

        # MySQL 直连配置
        self.mysql_enabled = settings.java_mysql_enabled
        self.mysql_config = {
            "host": settings.java_mysql_host,
            "port": settings.java_mysql_port,
            "user": settings.java_mysql_user,
            "password": settings.java_mysql_password,
            "program_db": settings.java_mysql_program_db,
            "order_db": settings.java_mysql_order_db,
        }
        self._mysql_conn = None

    def _request(self, method: str, path: str, data: dict = None, base_url: str = None) -> dict | None:
        """发送请求到 Java API"""
        if not self.enabled:
            return None

        url = f"{(base_url or self.base_url)}{path}"
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            resp = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            # Java ApiResponse 格式: {"code": "0", "data": ..., "message": "success"}
            # 注意：code 可能是字符串 "0" 或整数 0
            if str(result.get("code")) == "0":
                return result.get("data")
            else:
                logger.warning(f"Java API 错误: {result.get('message')}")
                return None
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Java API 连接失败: {url}，回退到模拟数据: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"Java API 超时: {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Java API 异常: {type(e).__name__}: {e}")
            return None

    # ==================== MySQL 直连方法 ====================

    def _get_mysql_conn(self):
        """获取 MySQL 连接"""
        if self._mysql_conn is None or not self._mysql_conn.open:
            try:
                import pymysql
                self._mysql_conn = pymysql.connect(
                    host=self.mysql_config["host"],
                    port=self.mysql_config["port"],
                    user=self.mysql_config["user"],
                    password=self.mysql_config["password"],
                    database=self.mysql_config["program_db"],
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                )
            except Exception as e:
                logger.warning(f"MySQL 连接失败: {e}")
                return None
        return self._mysql_conn

    def _get_area_id_by_name(self, city_name: str) -> int | None:
        """根据城市名获取 area_id"""
        conn = self._get_mysql_conn()
        if not conn:
            return None

        try:
            # 切换到 base_data 数据库
            cursor = conn.cursor()
            cursor.execute("USE damai_base_data")
            cursor.execute("SELECT id FROM d_area WHERE name = %s", (city_name,))
            row = cursor.fetchone()
            # 切换回 program 数据库
            cursor.execute(f"USE {self.mysql_config['program_db']}")
            return row["id"] if row else None
        except Exception as e:
            logger.warning(f"查询 area_id 失败: {e}")
            return None

    def mysql_search_program(self, content: str = "", area_id: int = None,
                             category_id: int = None, city: str = "",
                             page: int = 1, size: int = 10) -> dict | None:
        """MySQL 直连搜索节目"""
        conn = self._get_mysql_conn()
        if not conn:
            return None

        # 如果提供了城市名，转换为 area_id
        if city and not area_id:
            area_id = self._get_area_id_by_name(city)

        try:
            cursor = conn.cursor()
            # 构建查询条件
            conditions = []
            params = []
            if content:
                conditions.append("(title LIKE %s OR actor LIKE %s)")
                params.extend([f"%{content}%", f"%{content}%"])
            if area_id:
                conditions.append("area_id = %s")
                params.append(area_id)
            if category_id:
                conditions.append("program_category_id = %s")
                params.append(category_id)

            where = " AND ".join(conditions) if conditions else "1=1"

            # 查询总数
            count_sql = f"SELECT COUNT(*) as total FROM d_program_0 WHERE {where}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["total"]

            # 查询数据
            offset = (page - 1) * size
            data_sql = f"SELECT id, title, actor, place, area_id, program_category_id, create_time FROM d_program_0 WHERE {where} LIMIT %s OFFSET %s"
            params.extend([size, offset])
            cursor.execute(data_sql, params)
            rows = cursor.fetchall()

            # 转换为标准格式
            records = []
            for row in rows:
                records.append({
                    "id": str(row["id"]),
                    "title": row.get("title", ""),
                    "actor": row.get("actor", ""),
                    "place": row.get("place", ""),
                    "areaId": str(row.get("area_id", "")),
                    "programCategoryId": str(row.get("program_category_id", "")),
                    "showTime": str(row.get("create_time", "")),
                })

            return {"totalSize": str(total), "list": records}
        except Exception as e:
            logger.warning(f"MySQL 查询失败: {e}")
            return None

    def mysql_get_program_detail(self, program_id: int) -> dict | None:
        """MySQL 直连获取节目详情"""
        conn = self._get_mysql_conn()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM d_program_0 WHERE id = %s", (program_id,))
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": str(row["id"]),
                "title": row.get("title", ""),
                "actor": row.get("actor", ""),
                "place": row.get("place", ""),
                "areaId": str(row.get("area_id", "")),
                "programCategoryId": str(row.get("program_category_id", "")),
                "showTime": str(row.get("create_time", "")),
                "detail": row.get("detail", ""),
                "refundTicketRule": row.get("refund_ticket_rule", ""),
                "entryRule": row.get("entry_rule", ""),
                "childPurchase": row.get("child_purchase", ""),
            }
        except Exception as e:
            logger.warning(f"MySQL 查询失败: {e}")
            return None

    def mysql_get_ticket_categories(self, program_id: int) -> list | None:
        """MySQL 直连获取票档列表"""
        conn = self._get_mysql_conn()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, program_id, introduce, price, total_number, remain_number FROM d_ticket_category_0 WHERE program_id = %s",
                (program_id,)
            )
            rows = cursor.fetchall()

            return [{
                "id": str(row["id"]),
                "programId": str(row["program_id"]),
                "introduce": row.get("introduce", ""),
                "price": str(row.get("price", "")),
                "totalNumber": str(row.get("total_number", "")),
                "remainNumber": str(row.get("remain_number", "")),
            } for row in rows]
        except Exception as e:
            logger.warning(f"MySQL 查询失败: {e}")
            return None

    # ==================== 节目相关（HTTP API）====================

    def search_program(self, content: str = "", area_id: int = None,
                       category_id: int = None, city: str = "",
                       page: int = 1, size: int = 10) -> dict | None:
        """搜索节目（优先 MySQL 直连，其次 HTTP API）"""
        # 优先使用 MySQL 直连
        if self.mysql_enabled:
            result = self.mysql_search_program(content, area_id, category_id, city, page, size)
            if result and result.get("list"):
                return result
            logger.info("MySQL 直连无结果，尝试 HTTP API")

        # 回退到 HTTP API
        data = {"content": content, "pageNumber": page, "pageSize": size, "timeType": 1}
        if area_id:
            data["areaId"] = area_id
        if category_id:
            data["programCategoryId"] = category_id
        return self._request("POST", "/program/search", data, base_url=self.program_url)

    def get_program_detail(self, program_id: int) -> dict | None:
        """获取节目详情（优先 MySQL 直连，其次 HTTP API）"""
        # 优先使用 MySQL 直连
        if self.mysql_enabled:
            result = self.mysql_get_program_detail(program_id)
            if result:
                return result
            logger.info("MySQL 直连无结果，尝试 HTTP API")

        # 回退到 HTTP API
        return self._request("POST", "/program/detail", {"id": program_id}, base_url=self.program_url)

    def get_home_list(self) -> list | None:
        """获取首页节目列表"""
        data = self._request("POST", "/program/home/list", {"current": 1, "size": 10}, base_url=self.program_url)
        return data if data else None

    def get_recommend_list(self) -> list | None:
        """获取推荐节目列表"""
        data = self._request("POST", "/program/recommend/list", {"current": 1, "size": 5}, base_url=self.program_url)
        return data if data else None

    # ==================== 票档相关 ====================

    def get_ticket_categories(self, program_id: int) -> list | None:
        """获取节目票档列表（优先 MySQL 直连，其次 HTTP API）"""
        # 优先使用 MySQL 直连
        if self.mysql_enabled:
            result = self.mysql_get_ticket_categories(program_id)
            if result:
                return result
            logger.info("MySQL 直连无结果，尝试 HTTP API")

        # 回退到 HTTP API
        return self._request("POST", "/ticket/category/select/list/by/program", {"programId": program_id}, base_url=self.program_url)

    # ==================== 订单相关 ====================

    def create_order(self, program_id: int, ticket_category_id: int,
                     ticket_count: int, mobile: str) -> dict | None:
        """创建订单"""
        data = {
            "programId": program_id,
            "ticketCategoryId": ticket_category_id,
            "ticketCount": ticket_count,
            "mobile": mobile,
        }
        return self._request("POST", "/order/create", data, base_url=self.order_url)

    def get_order(self, order_number: str) -> dict | None:
        """查询订单详情"""
        return self._request("POST", "/order/get", {"orderNumber": order_number}, base_url=self.order_url)

    def get_order_list(self, mobile: str = "", page: int = 1, size: int = 10) -> dict | None:
        """查询订单列表"""
        data = {"current": page, "size": size}
        if mobile:
            data["mobile"] = mobile
        return self._request("POST", "/order/select/list", data, base_url=self.order_url)

    # ==================== 区域相关 ====================

    def get_area_list(self) -> list | None:
        """获取区域列表（城市）"""
        return self._request("POST", "/area/select/list", {}, base_url=self.program_url)

    # ==================== 节目分类相关 ====================

    def get_category_list(self) -> list | None:
        """获取节目分类列表"""
        return self._request("POST", "/program/category/select/list", {}, base_url=self.program_url)


# 全局单例
java_api = JavaAPIClient()
