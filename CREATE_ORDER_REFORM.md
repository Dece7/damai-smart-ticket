# create_order 改造方案

## 当前问题

1. **参数不匹配**：函数接收ticket_price，但API需要ticket_category_id
2. **缺少用户ID**：没有从Token获取当前用户的userId
3. **缺少购票人信息**：创建订单需要ticketUserIdList
4. **风险高**：直接下单可能导致误操作

## 改造方案

### 方案一：改为"下单引导"功能（推荐）

将create_order改造为create_order_guide，不直接下单，而是：
1. 查询节目和票档信息
2. 生成下单链接
3. 引导用户跳转到全栈项目完成下单

### 方案二：完善create_order

保留create_order，但需要：
1. 从Token获取userId
2. 查询用户的购票人列表
3. 添加确认机制
