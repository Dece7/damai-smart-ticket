# Java 项目整合方案

> Python AI 项目与 Java 微服务票务系统打通，实现真实业务数据联动。

---

## 整合架构

```
用户 → 统一前端
         ├→ Java 后端（业务逻辑：节目、订单、支付、用户）
         └→ Python AI 后端（智能交互：Agent、RAG、MCP）
              ↓ HTTP / MySQL 直连
           Java 数据库
```

## 两种数据接入方式

| 方式 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **HTTP API** | Python 调用 Java 微服务 REST API | 标准方式，Java 服务可独立部署 | 依赖 ES，数据可能不完整 |
| **MySQL 直连** | Python 直接查询 Java 数据库 | 绕过 ES，数据完整 | 耦合度高，需知道表结构 |

**本项目两种都实现了**，MySQL 直连为主，HTTP API 为备。

## 已打通的功能

| 功能 | 数据来源 | 状态 |
|------|---------|------|
| 节目搜索 | MySQL `damai_program_0.d_program_0`（26 条） | ✅ |
| 票档查询 | MySQL `d_ticket_category_0` | ✅ |
| 节目详情 | MySQL 直连 + HTTP API 双模式 | ✅ |
| 城市映射 | MySQL `damai_base_data.d_area` | ✅ |
| 下单 | 需要用户登录态 | ⚠️ 待整合 |

## 核心代码

```python
# Java API 客户端（双模式）
class JavaAPIClient:
    def search_program(self, content, city="", ...):
        # 优先 MySQL 直连
        if self.mysql_enabled:
            result = self.mysql_search_program(content, city=city)
            if result:
                return result
        # 回退到 HTTP API
        return self._request("POST", "/program/search", data)

    def mysql_search_program(self, content, city="", ...):
        # 城市名 → area_id 映射
        area_id = self._get_area_id_by_name(city)
        # 查询节目表
        cursor.execute("SELECT * FROM d_program_0 WHERE area_id = %s", (area_id,))
```

## 双模式设计

```python
# .env 配置
JAVA_API_ENABLED=true          # 启用 Java API
JAVA_MYSQL_ENABLED=true        # 启用 MySQL 直连
JAVA_MYSQL_PROGRAM_DB=damai_program_0
JAVA_API_PROGRAM_URL=http://localhost:6086
```

工具函数自动回退：
```python
@tool
def search_program(city, category, ...):
    # 优先 Java API
    if java_api.enabled:
        result = java_api.search_program(content, city=city)
        if result:
            return result
    # 回退到模拟数据
    return mock_data
```

## 面试话术💥

> "Python AI 项目通过两种方式整合 Java 后端：HTTP API 调用微服务 + MySQL 直连查询数据库。MySQL 直连是为了绕过 ES 数据不完整的问题。工具函数支持双模式——Java API 可用时调用真实接口，不可用时自动回退到模拟数据，保证系统始终可用。通过 MCP 协议封装，第三方客户端也能即插即用调用 Java 服务能力。"
