"""模拟数据 - 对应原项目的 ES 数据库和外部 API"""

PROGRAMS = [
    {"id": 1, "name": "周杰伦嘉年华世界巡回演唱会-北京站", "city": "北京", "category": "演唱会", "actor": "周杰伦", "venue": "国家体育场（鸟巢）", "showTime": "2026-08-15 19:30", "priceRange": "380-1880"},
    {"id": 2, "name": "林俊杰JJ20世界巡回演唱会-北京站", "city": "北京", "category": "演唱会", "actor": "林俊杰", "venue": "凯迪拉克中心", "showTime": "2026-09-20 19:30", "priceRange": "280-1680"},
    {"id": 3, "name": "张学友60+巡回演唱会-上海站", "city": "上海", "category": "演唱会", "actor": "张学友", "venue": "梅赛德斯-奔驰文化中心", "showTime": "2026-07-10 19:30", "priceRange": "480-2080"},
    {"id": 4, "name": "草莓音乐节-北京站", "city": "北京", "category": "音乐节", "actor": "多位艺人", "venue": "北京世园公园", "showTime": "2026-05-01 10:00", "priceRange": "299-599"},
    {"id": 5, "name": "开心麻花话剧《乌龙山伯爵》", "city": "北京", "category": "话剧", "actor": "开心麻花", "venue": "海淀剧院", "showTime": "2026-06-15 19:30", "priceRange": "180-680"},
    {"id": 6, "name": "薛之谦天外来物巡回演唱会-广州站", "city": "广州", "category": "演唱会", "actor": "薛之谦", "venue": "广州天河体育中心", "showTime": "2026-10-05 19:30", "priceRange": "380-1580"},
    {"id": 7, "name": "五月天人生无限公司演唱会-深圳站", "city": "深圳", "category": "演唱会", "actor": "五月天", "venue": "深圳湾体育中心", "showTime": "2026-11-12 19:30", "priceRange": "355-1855"},
    {"id": 8, "name": "德云社相声专场-北京站", "city": "北京", "category": "相声", "actor": "德云社", "venue": "德云社剧场", "showTime": "2026-06-20 19:00", "priceRange": "100-380"},
]

TICKET_CATEGORIES = {
    1: [
        {"id": 101, "name": "内场VIP", "price": 1880, "remain": 50, "total": 200},
        {"id": 102, "name": "内场", "price": 1280, "remain": 120, "total": 500},
        {"id": 103, "name": "看台A区", "price": 880, "remain": 200, "total": 800},
        {"id": 104, "name": "看台B区", "price": 380, "remain": 300, "total": 1000},
    ],
    2: [
        {"id": 201, "name": "内场VIP", "price": 1680, "remain": 30, "total": 150},
        {"id": 202, "name": "内场", "price": 1080, "remain": 80, "total": 400},
        {"id": 203, "name": "看台A区", "price": 680, "remain": 150, "total": 600},
        {"id": 204, "name": "看台B区", "price": 280, "remain": 250, "total": 800},
    ],
    3: [
        {"id": 301, "name": "内场VIP", "price": 2080, "remain": 20, "total": 100},
        {"id": 302, "name": "内场", "price": 1480, "remain": 60, "total": 300},
        {"id": 303, "name": "看台A区", "price": 980, "remain": 180, "total": 500},
        {"id": 304, "name": "看台B区", "price": 480, "remain": 300, "total": 900},
    ],
    4: [
        {"id": 401, "name": "单日票", "price": 299, "remain": 500, "total": 2000},
        {"id": 402, "name": "三日通票", "price": 599, "remain": 200, "total": 1000},
    ],
    5: [
        {"id": 501, "name": "VIP区", "price": 680, "remain": 40, "total": 100},
        {"id": 502, "name": "A区", "price": 380, "remain": 100, "total": 300},
        {"id": 503, "name": "B区", "price": 180, "remain": 200, "total": 500},
    ],
    6: [
        {"id": 601, "name": "内场VIP", "price": 1580, "remain": 40, "total": 200},
        {"id": 602, "name": "看台A区", "price": 880, "remain": 150, "total": 500},
        {"id": 603, "name": "看台B区", "price": 380, "remain": 300, "total": 1000},
    ],
    7: [
        {"id": 701, "name": "内场VIP", "price": 1855, "remain": 25, "total": 150},
        {"id": 702, "name": "看台A区", "price": 1055, "remain": 100, "total": 400},
        {"id": 703, "name": "看台B区", "price": 355, "remain": 250, "total": 800},
    ],
    8: [
        {"id": 801, "name": "前排VIP", "price": 380, "remain": 20, "total": 50},
        {"id": 802, "name": "普通座", "price": 180, "remain": 80, "total": 200},
        {"id": 803, "name": "后排", "price": 100, "remain": 150, "total": 300},
    ],
}

USERS = {
    "13800138000": {"id": 1001, "name": "张三", "mobile": "13800138000"},
    "13900139000": {"id": 1002, "name": "李四", "mobile": "13900139000"},
}

# 会员信息
MEMBERS = {
    "13800138000": {"level": "金卡", "points": 5200, "discount": 0.9},
    "13900139000": {"level": "银卡", "points": 2100, "discount": 0.95},
}

# 会员折扣规则
MEMBER_DISCOUNTS = {
    "普通": 1.0,
    "银卡": 0.95,
    "金卡": 0.9,
    "钻石": 0.85,
}

# 订单存储
ORDERS = {}

ORDER_COUNTER = [10000]
