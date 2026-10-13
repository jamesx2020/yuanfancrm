import csv, io
from flask import Blueprint, jsonify, request, g, Response
from sqlalchemy import select, func, delete
from werkzeug.security import generate_password_hash
from werkzeug.exceptions import BadRequest, Forbidden
from app.extensions import db
from app.models import *
from app.utils import text, integer, cents, day, currency, choice, today
from app.services import serialization as ser
from app.services.access import role, get, customer, order, quote, assignee
from app.services.audit import audit
from app.services.quotation import create_quote, copy_quote, convert
STAGES=['新询盘','需求确认','已报价','样品 / 谈判','待确认订单','赢单','丢单']

def customers_query():
    q=select(Customer).order_by(Customer.id.desc())
    if g.user.role=='sales': q=q.where(Customer.owner_id==g.user.id)
    return q


def accessible_orders():
    q=select(Order).order_by(Order.id.desc())
    if g.user.role=='sales': q=q.join(Customer).where(Customer.owner_id==g.user.id)
    elif g.user.role=='procurement':
        ids=select(OrderLine.order_id).join(SupplyTask,SupplyTask.order_line_id==OrderLine.id).where(SupplyTask.assignee_id==g.user.id)
        q=q.where(Order.id.in_(ids))
    return db().scalars(q).all()


def allowed_owner(value):
    id=integer(value or g.user.id,1)
    if g.user.role=='sales' and id!=g.user.id: raise Forbidden('业务员只能创建本人负责的客户')
    u=get(User,id)
    if not u.active or u.role not in ['admin','sales']: raise BadRequest('客户负责人必须为有效管理员或业务员')
    return id


def contact_data(d):
    email=text(d,'email',limit=200).lower()
    if email and ('@' not in email or '\n' in email): raise BadRequest('邮箱格式不正确')
    return dict(name=text(d,'name',True,100),email=email,phone=text(d,'phone',limit=80),position=text(d,'position',limit=80))


