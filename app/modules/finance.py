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
bp=Blueprint('finance',__name__)

@bp.post('/api/orders/<int:id>/payments')
def payment_create(id):
    role('admin','finance');o=order(id);d=request.get_json();key=text(d,'request_key',True,80)
    existing=db().scalar(select(Payment).where(Payment.request_key==key))
    if existing:
        if existing.order_id!=o.id: raise BadRequest('请求标识已用于其他订单')
        return jsonify(ser.base(existing))
    amount=cents(d.get('amount'))
    summary=ser.order(o)
    if amount<=0 or amount>summary['balance']: raise BadRequest('到账金额必须大于零且不超过剩余应收')
    p=Payment(order_id=id,amount=amount,paid_date=day(d.get('paid_date')),note=text(d,'note',limit=2000),request_key=key,user_id=g.user.id);db().add(p);audit('登记收款',p);return jsonify(ser.base(p)),201


@bp.post('/api/payments/<int:id>/void')
def payment_void(id):
    role('admin','finance');p=get(Payment,id);order(p.order_id)
    if p.voided: raise BadRequest('该收款记录已经作废')
    p.void_reason=text(request.get_json(),'reason',True,2000);p.voided=True;audit('作废收款',p,{'reason':p.void_reason});return jsonify(ser.base(p))


@bp.post('/api/orders/<int:id>/shipments')
def shipment_create(id):
    role('admin','sales');o=order(id,True);d=request.get_json();key=text(d,'request_key',True,80)
    existing=db().scalar(select(Shipment).where(Shipment.request_key==key))
    if existing:
        if existing.order_id!=o.id: raise BadRequest('请求标识已用于其他订单')
        return jsonify(ser.base(existing))
    lines=d.get('lines',[])
    if not isinstance(lines,list) or not 1<=len(lines)<=100: raise BadRequest('请填写出货产品及数量')
    validated=[];seen=set()
    for ld in lines:
        l=get(OrderLine,integer(ld.get('order_line_id'),1));qty=integer(ld.get('quantity'),1,1000000)
        if l.order_id!=id or l.id in seen: raise BadRequest('出货产品不合法或重复')
        seen.add(l.id)
        shipped=db().scalar(select(func.coalesce(func.sum(ShipmentLine.quantity),0)).where(ShipmentLine.order_line_id==l.id))
        if shipped+qty>l.quantity: raise BadRequest('出货数量超过剩余数量')
        validated.append((l.id,qty))
    s=Shipment(order_id=id,tracking=text(d,'tracking',True),ship_date=day(d.get('ship_date')),destination=text(d,'destination'),user_id=g.user.id,request_key=key);db().add(s);db().flush()
    for lid,qty in validated: db().add(ShipmentLine(shipment_id=s.id,order_line_id=lid,quantity=qty))
    audit('登记出货',s);return jsonify(ser.base(s)),201


