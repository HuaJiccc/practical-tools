"""单位换算：纯本地算术，不联网。

每个单位都是一次仿射变换，落到本类的基准单位上：

    base = value * factor + offset

除了温度，其余类别 offset 都是 0 —— 留着这个字段是为了让温度也走同一个
公式，而不用在换算里写特例。前端拿到同一份表，套同样两行公式即可。

汇率不在这里算：它要走网络、会过期，交给 ``currency`` 模块。
"""

CATEGORIES = [
    {"id": "length", "name": "长度", "base": "米", "default_from": "m", "default_to": "cm",
     "units": [
         {"id": "mm", "name": "毫米", "symbol": "mm", "factor": 0.001},
         {"id": "cm", "name": "厘米", "symbol": "cm", "factor": 0.01},
         {"id": "m", "name": "米", "symbol": "m", "factor": 1.0},
         {"id": "km", "name": "千米", "symbol": "km", "factor": 1000.0},
         {"id": "in", "name": "英寸", "symbol": "in", "factor": 0.0254},
         {"id": "ft", "name": "英尺", "symbol": "ft", "factor": 0.3048},
         {"id": "yd", "name": "码", "symbol": "yd", "factor": 0.9144},
         {"id": "mi", "name": "英里", "symbol": "mi", "factor": 1609.344},
     ]},
    {"id": "mass", "name": "重量", "base": "千克", "default_from": "kg", "default_to": "g",
     "units": [
         {"id": "mg", "name": "毫克", "symbol": "mg", "factor": 1e-06},
         {"id": "g", "name": "克", "symbol": "g", "factor": 0.001},
         {"id": "kg", "name": "千克", "symbol": "kg", "factor": 1.0},
         {"id": "t", "name": "吨", "symbol": "t", "factor": 1000.0},
         {"id": "oz", "name": "盎司", "symbol": "oz", "factor": 0.028349523125},
         {"id": "lb", "name": "磅", "symbol": "lb", "factor": 0.45359237},
     ]},
    {"id": "area", "name": "面积", "base": "平方米", "default_from": "m2", "default_to": "cm2",
     "units": [
         {"id": "mm2", "name": "平方毫米", "symbol": "mm²", "factor": 1e-06},
         {"id": "cm2", "name": "平方厘米", "symbol": "cm²", "factor": 0.0001},
         {"id": "m2", "name": "平方米", "symbol": "m²", "factor": 1.0},
         {"id": "km2", "name": "平方千米", "symbol": "km²", "factor": 1000000.0},
         {"id": "ft2", "name": "平方英尺", "symbol": "ft²", "factor": 0.09290304},
         {"id": "in2", "name": "平方英寸", "symbol": "in²", "factor": 0.00064516},
         {"id": "mu", "name": "亩", "symbol": "亩", "factor": 666.6666666666666},
         {"id": "ha", "name": "公顷", "symbol": "ha", "factor": 10000.0},
     ]},
    {"id": "volume", "name": "体积", "base": "升", "default_from": "l", "default_to": "ml",
     "units": [
         {"id": "ml", "name": "毫升", "symbol": "mL", "factor": 0.001},
         {"id": "cm3", "name": "立方厘米", "symbol": "cm³", "factor": 0.001},
         {"id": "l", "name": "升", "symbol": "L", "factor": 1.0},
         {"id": "m3", "name": "立方米", "symbol": "m³", "factor": 1000.0},
         {"id": "gal_us", "name": "加仑（美）", "symbol": "gal", "factor": 3.785411784},
         {"id": "gal_uk", "name": "加仑（英）", "symbol": "gal", "factor": 4.54609},
         {"id": "pt_us", "name": "品脱（美）", "symbol": "pt", "factor": 0.473176473},
     ]},
    {"id": "temperature", "name": "温度", "base": "摄氏度", "default_from": "c", "default_to": "f",
     "units": [
         {"id": "c", "name": "摄氏度", "symbol": "°C", "factor": 1.0, "offset": 0.0},
         {"id": "f", "name": "华氏度", "symbol": "°F", "factor": 0.5555555555555556,
          "offset": -17.77777777777778},
         {"id": "k", "name": "开尔文", "symbol": "K", "factor": 1.0, "offset": -273.15},
     ]},
    {"id": "speed", "name": "速度", "base": "米/秒", "default_from": "kmh", "default_to": "ms",
     "units": [
         {"id": "ms", "name": "米/秒", "symbol": "m/s", "factor": 1.0},
         {"id": "kmh", "name": "千米/小时", "symbol": "km/h", "factor": 0.2777777777777778},
         {"id": "mph", "name": "英里/小时", "symbol": "mph", "factor": 0.44704},
         {"id": "knot", "name": "节", "symbol": "kn", "factor": 0.5144444444444445},
     ]},
    {"id": "data", "name": "数据存储", "base": "字节", "default_from": "mb", "default_to": "gb",
     "units": [
         {"id": "b", "name": "字节", "symbol": "B", "factor": 1.0},
         {"id": "kb", "name": "千字节", "symbol": "KB", "factor": 1024.0},
         {"id": "mb", "name": "兆字节", "symbol": "MB", "factor": 1048576.0},
         {"id": "gb", "name": "吉字节", "symbol": "GB", "factor": 1073741824.0},
         {"id": "tb", "name": "太字节", "symbol": "TB", "factor": 1099511627776.0},
     ]},
]

CURRENCY_ID = "currency"

# 汇率是动态的（要联网拉表），所以只给一个占位类别，单位表由 currency 模块填
CURRENCY_CATEGORY = {
    "id": CURRENCY_ID,
    "name": "汇率",
    "base": "USD",
    "default_from": "USD",
    "default_to": "CNY",
    "dynamic": True,
}

_CATEGORY_MAP = {item["id"]: item for item in CATEGORIES}


def category(category_id):
    """按 id 取一个类别，没有则 None。"""
    return _CATEGORY_MAP.get(category_id)


def unit(category_id, unit_id):
    """取类别下的某个单位定义，没有则 None。"""
    group = _CATEGORY_MAP.get(category_id)
    if not group:
        return None
    for item in group["units"]:
        if item["id"] == unit_id:
            return item
    return None


def to_base(value, unit_def):
    """换算到本类别的基准单位。"""
    return value * unit_def["factor"] + unit_def.get("offset", 0.0)


def from_base(base_value, unit_def):
    """从基准单位换算到目标单位。"""
    return (base_value - unit_def.get("offset", 0.0)) / unit_def["factor"]


def convert(value, category_id, from_id, to_id):
    """同一类别内换算。类别或单位不存在时抛 ValueError（界面据此提示）。"""
    src = unit(category_id, from_id)
    dst = unit(category_id, to_id)
    if not src or not dst:
        raise ValueError("未知单位")
    if from_id == to_id:
        return float(value)
    return from_base(to_base(value, src), dst)


def parse_number(text):
    """把用户输入变成数字，认不出就 None。允许千分位逗号与前后空格。"""
    raw = str(text or "").strip().replace(",", "").replace("，", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def format_number(value, max_decimals=6):
    """最多保留 ``max_decimals`` 位小数，去掉结尾的 0。

    极大或极小的数改用科学计数法，否则会变成一长串 0 或者直接显示成 0。
    """
    number = float(value)
    if number == 0:
        return "0"
    magnitude = abs(number)
    if magnitude >= 1e16 or magnitude < 1e-6:
        text = f"{number:.5e}"          # 1.234568e+17
        mantissa, _, exponent = text.partition("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        sign = ""
        if exponent.startswith("+"):
            exponent = exponent[1:]
        elif exponent.startswith("-"):
            sign, exponent = "-", exponent[1:]
        return f"{mantissa}e{sign}{exponent}"
    text = f"{number:.{int(max_decimals)}f}".rstrip("0").rstrip(".")
    return text or "0"


def catalogue():
    """给前端的完整表：静态类别 + 一个待填的汇率类别。"""
    return CATEGORIES + [CURRENCY_CATEGORY]
