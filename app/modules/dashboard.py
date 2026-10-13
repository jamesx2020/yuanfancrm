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
bp=Blueprint('dashboard',__name__)

@bp.get('/api/bootstrap')
def bootstrap():
    role_name=g.user.role
    customers=[] if role_name=='procurement' else db().scalars(customers_query()).all()
    ids=[c.id for c in customers]
    ops=db().scalars(select(Opportunity).where(Opportunity.customer_id.in_(ids)).order_by(Opportunity.id.desc())).all() if role_name in ['admin','sales'] else []
    qs=db().scalars(select(Quotation).where(Quotation.customer_id.in_(ids)).order_by(Quotation.id.desc())).all() if role_name in ['admin','sales'] else []
    tasks=db().scalars(select(Task).where(Task.user_id==g.user.id).order_by(Task.due_date,Task.id)).all()
    products=db().scalars(select(Product).where(Product.archived==False).order_by(Product.id.desc())).all() if role_name in ['admin','sales','procurement'] else []
    # Directory contains names and roles only, never password hashes or usernames.
    people=[{k:getattr(u,k) for k in ['id','name','role','active']} for u in db().scalars(select(User).where(User.active==True))]
    return jsonify(user=ser.user(g.user),today=today(),customers=[ser.customer(c) for c in customers],opportunities=[ser.base(o) for o in ops],quotes=[ser.quotation(q) for q in qs],orders=[ser.order(o) for o in accessible_orders()],tasks=[ser.base(t) for t in tasks],products=[ser.product(p) for p in products],suppliers=[ser.base(s) if role_name in ['admin','procurement'] else {'id':s.id,'name':s.name} for s in db().scalars(select(Supplier))] if role_name in ['admin','procurement','sales'] else [],people=people)


@bp.post('/api/tasks')
def task_create():
    d=request.get_json();c=None
    if d.get('customer_id'): c=customer(integer(d['customer_id'],1))
    t=Task(customer_id=c.id if c else None,user_id=g.user.id,title=text(d,'title',True,300),due_date=day(d.get('due_date')));db().add(t);audit('新建待办',t);return jsonify(ser.base(t)),201


@bp.patch('/api/tasks/<int:id>')
def task_update(id):
    t=get(Task,id)
    if t.user_id!=g.user.id: raise Forbidden('只能修改自己的待办')
    d=request.get_json()
    if 'done' in d:
        if not isinstance(d['done'],bool): raise BadRequest('完成状态必须为布尔值')
        t.done=d['done']
    if 'due_date' in d: t.due_date=day(d['due_date'])
    audit('更新待办',t);return jsonify(ser.base(t))


@bp.get('/api/reports')
def reports():
    role('admin','sales','finance');cs=db().scalars(customers_query()).all();ids=[c.id for c in cs];os=accessible_orders();by_currency={}
    for o in os:
        s=ser.order(o);group=by_currency.setdefault(o.currency,{'orders':0,'amount':0,'paid':0,'balance':0})
        group['orders']+=1
        for k in ['amount','paid','balance']: group[k]+=s[k]
    ops=db().scalars(select(Opportunity).where(Opportunity.customer_id.in_(ids))).all() if g.user.role!='finance' else []
    stage_counts={s:sum(1 for o in ops if o.stage==s) for s in STAGES}
    monthly={}
    for o in os:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        key=datetime.fromisoformat(o.created_at).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m')+' / '+o.currency;monthly[key]=monthly.get(key,0)+ser.order(o)['amount']
    countries={}
    for c in cs: countries[c.country]=countries.get(c.country,0)+1
    return jsonify(customers=len(cs),by_currency=by_currency,stages=stage_counts,monthly=monthly,countries=countries)


