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
from app.modules.common import customers_query, accessible_orders, allowed_owner, contact_data, STAGES
bp=Blueprint('orders',__name__)

@bp.patch('/api/orders/<int:id>')
def order_update(id):
    o=order(id,True);d=request.get_json()
    if 'due_date' in d: o.due_date=day(d['due_date'])
    if 'status' in d: o.status=choice(d['status'],['待安排供货','供货执行中','待出货','已完成'])
    audit('更新订单',o);return jsonify(ser.order(o))


@bp.post('/api/orders/<int:id>/supply')
def supply_create(id):
    role('admin','sales');o=order(id,True);d=request.get_json();line=get(OrderLine,integer(d.get('order_line_id'),1))
    if line.order_id!=o.id: raise BadRequest('产品不属于该订单')
    quantity=integer(d.get('quantity'),1,1000000)
    allocated=db().scalar(select(func.coalesce(func.sum(SupplyTask.quantity),0)).where(SupplyTask.order_line_id==line.id))
    if allocated+quantity>line.quantity: raise BadRequest('分配数量超过订单产品数量')
    mode=choice(d.get('mode'),['自产','外采']);sid=get(Supplier,integer(d.get('supplier_id'),1)).id if mode=='外采' else None
    if g.user.role=='sales' and 'cost' in d: raise Forbidden('业务员不能设置供货成本')
    t=SupplyTask(order_line_id=line.id,mode=mode,supplier_id=sid,assignee_id=assignee(d.get('assignee_id')),quantity=quantity,cost=cents(d.get('cost',0)),due_date=day(d.get('due_date')));db().add(t);o.status='供货执行中';audit('创建供货任务',t);return jsonify(id=t.id),201


@bp.patch('/api/supply/<int:id>')
def supply_update(id):
    role('admin','procurement');t=get(SupplyTask,id)
    if g.user.role=='procurement' and t.assignee_id!=g.user.id: raise Forbidden('只能修改分配给本人的任务')
    d=request.get_json()
    if 'progress' in d: t.progress=integer(d['progress'],0,100)
    if 'quality' in d: t.quality=text(d,'quality',True)
    if 'cost' in d: t.cost=cents(d['cost'])
    if 'due_date' in d: t.due_date=day(d['due_date'])
    audit('更新供货进度',t);return jsonify(ser.base(t))


