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
bp=Blueprint('products',__name__)

@bp.post('/api/suppliers')
def supplier_create():
    role('admin','procurement');d=request.get_json();s=Supplier(name=text(d,'name',True),contact=text(d,'contact'),phone=text(d,'phone',limit=80));db().add(s);audit('创建供应商',s);return jsonify(ser.base(s)),201


@bp.post('/api/products')
def product_create():
    role('admin','procurement');d=request.get_json();p=Product(sku=text(d,'sku',True,80),name=text(d,'name',True),spec=text(d,'spec',limit=1000),unit=text(d,'unit',limit=30) or '件',mode=choice(d.get('mode','自产'),['自产','外采','混合供货']),cost=cents(d.get('cost',0)),currency=currency(d.get('currency','USD')));db().add(p);audit('创建产品',p);return jsonify(ser.product(p)),201


@bp.patch('/api/products/<int:id>')
def product_update(id):
    role('admin','procurement');p=get(Product,id);d=request.get_json()
    for k,limit in [('name',200),('sku',80),('spec',1000),('unit',30)]:
        if k in d: setattr(p,k,text(d,k,k in ['name','sku'],limit))
    if 'cost' in d: p.cost=cents(d['cost'])
    if 'mode' in d: p.mode=choice(d['mode'],['自产','外采','混合供货'])
    if 'archived' in d:
        if not isinstance(d['archived'],bool): raise BadRequest('归档值必须为布尔值')
        p.archived=d['archived']
    audit('更新产品',p);return jsonify(ser.product(p))


@bp.post('/api/products/<int:id>/sources')
def source_create(id):
    role('admin','procurement');get(Product,id);d=request.get_json();mode=choice(d.get('mode'),['自产','外采']);sid=None
    if mode=='外采': sid=get(Supplier,integer(d.get('supplier_id'),1)).id
    if db().scalar(select(ProductSource).where(ProductSource.product_id==id,ProductSource.mode==mode,ProductSource.supplier_id==sid)): raise BadRequest('该供货来源已经存在')
    s=ProductSource(product_id=id,mode=mode,supplier_id=sid,cost=cents(d.get('cost',0)));db().add(s);audit('增加产品供货来源',s);return jsonify(ser.base(s)),201


