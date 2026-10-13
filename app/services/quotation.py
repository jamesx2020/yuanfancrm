from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, func
from werkzeug.exceptions import BadRequest
from app.models import Quotation, QuoteLine, Order, OrderLine, Opportunity, Product
from app.extensions import db
from app.services.access import customer, get
from app.services.audit import audit
from app.utils import text, integer, cents, day, currency

def number(prefix): return prefix+'-'+datetime.now().strftime('%Y%m%d')+'-'+uuid4().hex[:8].upper()
def create_quote(data):
    c=customer(integer(data.get('customer_id'),1),write=True)
    if c.archived: raise BadRequest('客户已归档')
    opportunity_id=data.get('opportunity_id') or None
    if opportunity_id:
        op=get(Opportunity,integer(opportunity_id,1))
        if op.customer_id!=c.id: raise BadRequest('商机与客户不一致')
        opportunity_id=op.id
    lines=data.get('lines')
    if not isinstance(lines,list) or not 1<=len(lines)<=100: raise BadRequest('报价需包含 1–100 个产品')
    q=Quotation(customer_id=c.id,opportunity_id=opportunity_id,number=number('QT'),currency=currency(data.get('currency','USD')),valid_until=day(data.get('valid_until')),term=text(data,'term',True),payment_terms=text(data,'payment_terms',True,300),lead_time=text(data,'lead_time',True),notes=text(data,'notes',limit=5000))
    db().add(q); db().flush(); q.root_id=q.id
    for line in lines:
        pid=line.get('product_id') or None
        if pid: pid=get(Product,integer(pid,1)).id
        db().add(QuoteLine(quotation_id=q.id,product_id=pid,name=text(line,'name',True),spec=text(line,'spec',limit=1000),unit=text(line,'unit',limit=30) or '件',quantity=integer(line.get('quantity'),1,1000000),price=cents(line.get('price'))))
    audit('创建报价',q); return q

def copy_quote(q):
    v=(db().scalar(select(func.max(Quotation.version)).where(Quotation.root_id==q.root_id)) or 0)+1
    n=Quotation(customer_id=q.customer_id,opportunity_id=q.opportunity_id,number=number('QT'),root_id=q.root_id,version=v,currency=q.currency,valid_until=q.valid_until,term=q.term,payment_terms=q.payment_terms,lead_time=q.lead_time,notes=q.notes)
    db().add(n); db().flush()
    for l in db().scalars(select(QuoteLine).where(QuoteLine.quotation_id==q.id)):
        db().add(QuoteLine(quotation_id=n.id,product_id=l.product_id,name=l.name,spec=l.spec,unit=l.unit,quantity=l.quantity,price=l.price))
    audit('复制报价版本',n,{'source_id':q.id}); return n

def convert(q,due_date):
    existing=db().scalar(select(Order).where(Order.quotation_id==q.id))
    if existing: return existing
    if q.status=='已转订单': raise BadRequest('报价状态异常')
    o=Order(quotation_id=q.id,customer_id=q.customer_id,number=number('SO'),currency=q.currency,term=q.term,payment_terms=q.payment_terms,lead_time=q.lead_time,due_date=day(due_date))
    db().add(o); db().flush()
    for l in db().scalars(select(QuoteLine).where(QuoteLine.quotation_id==q.id)):
        db().add(OrderLine(order_id=o.id,product_id=l.product_id,name=l.name,spec=l.spec,unit=l.unit,quantity=l.quantity,price=l.price))
    q.status='已转订单'
    if q.opportunity_id: get(Opportunity,q.opportunity_id).stage='赢单'
    audit('报价转订单',o,{'quotation_id':q.id});return o
