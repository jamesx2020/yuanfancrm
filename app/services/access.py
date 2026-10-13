from flask import g
from sqlalchemy import select
from werkzeug.exceptions import Forbidden, NotFound, BadRequest
from app.extensions import db
from app.models import Customer, Order, OrderLine, SupplyTask, Quotation, User

def role(*roles):
    if g.user.role not in roles: raise Forbidden('当前角色没有该操作权限')
def get(model,id):
    obj=db().get(model,id)
    if obj is None: raise NotFound('记录不存在')
    return obj
def customer(id,write=False):
    c=get(Customer,id)
    if g.user.role=='sales' and c.owner_id!=g.user.id: raise Forbidden('只能访问本人负责的客户')
    if g.user.role=='procurement': raise Forbidden('采购生产人员不能访问客户档案')
    if write: role('admin','sales')
    return c
def order(id,write=False):
    o=get(Order,id)
    if g.user.role=='procurement':
        ids=db().scalars(select(SupplyTask.id).join(OrderLine,SupplyTask.order_line_id==OrderLine.id).where(OrderLine.order_id==o.id,SupplyTask.assignee_id==g.user.id)).all()
        if not ids: raise Forbidden('只能访问分配给本人的供货订单')
    else: customer(o.customer_id)
    if write: role('admin','sales')
    return o
def quote(id):
    role('admin','sales'); q=get(Quotation,id); customer(q.customer_id); return q
def assignee(id):
    u=get(User,id)
    if not u.active: raise BadRequest('不能分配给已停用人员')
    return u.id
