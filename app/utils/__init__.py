from datetime import date
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from datetime import datetime
from werkzeug.exceptions import BadRequest

def today(): return datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
def text(data,key,required=False,limit=200):
    value=data.get(key,'')
    if not isinstance(value,str): raise BadRequest(key+' 必须是文本')
    value=value.strip()
    if required and not value: raise BadRequest(key+' 不能为空')
    if len(value)>limit: raise BadRequest(key+' 长度超出限制')
    return value
def integer(value,minimum=0,maximum=1000000000):
    if isinstance(value,bool): raise BadRequest('请输入整数')
    try:
        d=Decimal(str(value))
        if not d.is_finite() or d!=d.to_integral_value() or d<minimum or d>maximum: raise ValueError()
        return int(d)
    except (ValueError,InvalidOperation): raise BadRequest('整数超出允许范围')
def cents(value):
    try:
        d=Decimal(str(value))
        if not d.is_finite() or d<0 or d>Decimal('1000000000') or d*100!=(d*100).to_integral_value(): raise ValueError()
        return int(d*100)
    except (InvalidOperation,ValueError): raise BadRequest('金额必须为非负数，最多两位小数')
def day(value,optional=False):
    if optional and not value: return ''
    try:
        if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value: raise ValueError()
        return value
    except (ValueError,TypeError): raise BadRequest('日期格式应为 YYYY-MM-DD')
def choice(value,allowed):
    if value not in allowed: raise BadRequest('不支持的选项：'+str(value))
    return value
def currency(value): return choice(value,['USD','EUR','CNY','GBP'])
