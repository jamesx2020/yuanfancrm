from flask import g
from sqlalchemy import select, func
from app.extensions import db
from app.models import *

def rows(model,**where): return db().scalars(select(model).filter_by(**where).order_by(model.id)).all()
def base(obj): return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}
def user(u): return {k:getattr(u,k) for k in ['id','username','name','role','active']}
def customer(c):
    d=base(c); d['owner']=db().get(User,c.owner_id).name; d['contacts']=[base(x) for x in rows(Contact,customer_id=c.id)]
    d['last_followup']=db().scalar(select(func.max(Followup.created_at)).where(Followup.customer_id==c.id)) or ''
    return d
def quotation(q):
    d=base(q);d['customer']=db().get(Customer,q.customer_id).name;d['lines']=[base(l) for l in rows(QuoteLine,quotation_id=q.id)];d['amount']=sum(l['quantity']*l['price'] for l in d['lines']);return d

def order(o):
    d=base(o); procurement=g.user.role=='procurement'
    d['customer']=db().get(Customer,o.customer_id).name
    lines=rows(OrderLine,order_id=o.id); d['lines']=[]
    for l in lines:
        ld=base(l);tasks=rows(SupplyTask,order_line_id=l.id)
        if procurement: tasks=[t for t in tasks if t.assignee_id==g.user.id]
        ld['tasks']=[]
        for t in tasks:
            td=base(t);td['assignee']=db().get(User,t.assignee_id).name;td['supplier']=db().get(Supplier,t.supplier_id).name if t.supplier_id else '自有工厂'
            if g.user.role=='sales': td.pop('cost',None)
            ld['tasks'].append(td)
        ld['shipped']=db().scalar(select(func.coalesce(func.sum(ShipmentLine.quantity),0)).where(ShipmentLine.order_line_id==l.id))
        if procurement: ld.pop('price');
        if not procurement or tasks: d['lines'].append(ld)
    if procurement:
        for key in ['currency','term','payment_terms','lead_time']: d.pop(key,None)
        return d
    d['amount']=sum(l.quantity*l.price for l in lines)
    d['payments']=[base(p) for p in rows(Payment,order_id=o.id)]
    d['paid']=sum(p['amount'] for p in d['payments'] if not p['voided'])
    d['balance']=d['amount']-d['paid']
    d['shipments']=[{**base(s),'lines':[base(sl) for sl in rows(ShipmentLine,shipment_id=s.id)]} for s in rows(Shipment,order_id=o.id)]
    d['quantity']=sum(l.quantity for l in lines);d['shipped']=sum(l['shipped'] for l in d['lines'])
    total=sum(l.quantity for l in lines)
    tasks=[t for l in lines for t in rows(SupplyTask,order_line_id=l.id)]
    d['supply_progress']=round(sum(t.quantity*t.progress for t in tasks)/total) if total else 0
    d['allocated']=sum(t.quantity for t in tasks)
    return d

def product(p):
    d=base(p);d['sources']=[{**base(s),'supplier':db().get(Supplier,s.supplier_id).name if s.supplier_id else '自有工厂'} for s in rows(ProductSource,product_id=p.id)]
    photos=[a for a in rows(Attachment,entity='products',entity_id=p.id) if a.storage_name.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
    d['image_id']=photos[0].id if photos else None
    if g.user.role=='sales':
        d.pop('cost',None)
        for s in d['sources']: s.pop('cost',None)
    return d
