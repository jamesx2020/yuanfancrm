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
bp=Blueprint('quotations',__name__)

@bp.post('/api/quotations')
def quotation_create():
    role('admin','sales');q=create_quote(request.get_json());return jsonify(ser.quotation(q)),201


@bp.post('/api/quotations/<int:id>/copy')
def quotation_copy(id): return jsonify(ser.quotation(copy_quote(quote(id)))),201


@bp.patch('/api/quotations/<int:id>')
def quotation_update(id):
    q=quote(id);d=request.get_json()
    if q.status=='已转订单': raise BadRequest('已转订单的报价不能修改，请创建新版本')
    if 'lines' in d:
        if q.status!='草稿': raise BadRequest('已发送报价需复制为新版本后修改')
        lines=d['lines']
        if not isinstance(lines,list) or not 1<=len(lines)<=100: raise BadRequest('报价需包含 1–100 个产品')
        db().execute(delete(QuoteLine).where(QuoteLine.quotation_id==q.id))
        for l in lines:
            pid=get(Product,integer(l['product_id'],1)).id if l.get('product_id') else None
            db().add(QuoteLine(quotation_id=q.id,product_id=pid,name=text(l,'name',True),spec=text(l,'spec',limit=1000),unit=text(l,'unit',limit=30) or '件',quantity=integer(l.get('quantity'),1,1000000),price=cents(l.get('price'))))
        for key,limit in [('term',200),('payment_terms',300),('lead_time',200),('notes',5000)]:
            if key in d: setattr(q,key,text(d,key,key!='notes',limit))
        if 'valid_until' in d: q.valid_until=day(d['valid_until'])
        if 'currency' in d: q.currency=currency(d['currency'])
    if 'status' in d: q.status=choice(d['status'],['草稿','已发送','待确认'])
    audit('更新报价',q);return jsonify(ser.quotation(q))


@bp.post('/api/quotations/<int:id>/convert')
def quotation_convert(id):
    q=quote(id);o=convert(q,request.get_json().get('due_date'));return jsonify(ser.order(o))


