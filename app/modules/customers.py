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
bp=Blueprint('customers',__name__)

@bp.post('/api/customers')
def customer_create():
    role('admin','sales');d=request.get_json();name=text(d,'name',True)
    c=Customer(name=name,name_key=name.casefold(),country=text(d,'country',True,80),website=text(d,'website',limit=300),source=text(d,'source',limit=80),level=choice(d.get('level','潜在客户'),['潜在客户','正式客户','重点客户']),product=text(d,'product'),owner_id=allowed_owner(d.get('owner_id')))
    db().add(c);db().flush()
    contacts=d.get('contacts',[])
    if not isinstance(contacts,list) or len(contacts)>20: raise BadRequest('联系人最多 20 个')
    for ct in contacts: db().add(Contact(customer_id=c.id,**contact_data(ct)))
    audit('创建客户',c);return jsonify(ser.customer(c)),201


@bp.patch('/api/customers/<int:id>')
def customer_update(id):
    c=customer(id,True);d=request.get_json()
    if 'name' in d: c.name=text(d,'name',True);c.name_key=c.name.casefold()
    for k,limit in [('country',80),('website',300),('source',80),('product',200)]:
        if k in d: setattr(c,k,text(d,k,limit=limit))
    if 'level' in d: c.level=choice(d['level'],['潜在客户','正式客户','重点客户'])
    if 'owner_id' in d:
        role('admin');previous=c.owner_id;c.owner_id=allowed_owner(d['owner_id'])
        for t in db().scalars(select(Task).where(Task.customer_id==c.id,Task.user_id==previous,Task.done==False)): t.user_id=c.owner_id
    if 'archived' in d:
        if not isinstance(d['archived'],bool): raise BadRequest('归档值必须为布尔值')
        c.archived=d['archived']
    audit('更新客户',c,{'fields':list(d)});return jsonify(ser.customer(c))


@bp.get('/api/customers/<int:id>')
def customer_detail(id):
    c=customer(id)
    return jsonify(**ser.customer(c),followups=[{**ser.base(f),'user':get(User,f.user_id).name} for f in db().scalars(select(Followup).where(Followup.customer_id==c.id).order_by(Followup.id.desc()))],attachments=[ser.base(a) for a in db().scalars(select(Attachment).where(Attachment.entity=='customers',Attachment.entity_id==id))])


@bp.post('/api/customers/<int:id>/contacts')
def contact_create(id):
    customer(id,True);ct=Contact(customer_id=id,**contact_data(request.get_json()));db().add(ct);audit('新增联系人',ct);return jsonify(ser.base(ct)),201


@bp.patch('/api/contacts/<int:id>')
def contact_update(id):
    ct=get(Contact,id);customer(ct.customer_id,True)
    for k,v in contact_data(request.get_json()).items(): setattr(ct,k,v)
    audit('更新联系人',ct);return jsonify(ser.base(ct))


@bp.post('/api/customers/<int:id>/followups')
def followup_create(id):
    c=customer(id,True);d=request.get_json();f=Followup(customer_id=id,user_id=g.user.id,content=text(d,'content',True,5000),channel=choice(d.get('channel','邮件'),['邮件','电话','WhatsApp','会议','其他']))
    db().add(f)
    if d.get('next_action'):
        db().add(Task(customer_id=id,user_id=c.owner_id,title=text(d,'next_action',True,300),due_date=day(d.get('due_date'))))
    audit('记录跟进',f);return jsonify(ser.base(f)),201


@bp.get('/api/customers/export')
def export_customers():
    role('admin','sales');buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['公司名称','国家','联系人','邮箱','客户类型','来源','关注产品'])
    def safe(v): return "'"+v if v and v[0] in '=+-@\t\r' else v
    for c in db().scalars(customers_query()):
        ct=db().scalar(select(Contact).where(Contact.customer_id==c.id).order_by(Contact.id))
        writer.writerow([safe(v or '') for v in [c.name,c.country,ct.name if ct else '',ct.email if ct else '',c.level,c.source,c.product]])
    return Response('\ufeff'+buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=customers.csv'})


@bp.post('/api/customers/import')
def import_customers():
    role('admin','sales');file=request.files.get('file')
    if not file: raise BadRequest('请选择 UTF-8 CSV 文件')
    try: content=file.read().decode('utf-8-sig');records=list(csv.DictReader(io.StringIO(content)))
    except (UnicodeError,csv.Error): raise BadRequest('请使用 UTF-8 编码的 CSV 文件')
    if not records or len(records)>2000: raise BadRequest('每次导入 1–2000 条记录')
    added=0;skipped=0
    for r in records:
        name=text(r,'公司名称',True)
        if db().scalar(select(Customer.id).where(Customer.name_key==name.casefold())): skipped+=1;continue
        c=Customer(name=name,name_key=name.casefold(),country=text(r,'国家',limit=80),source=text(r,'来源',limit=80),product=text(r,'关注产品'),owner_id=g.user.id,level=choice(r.get('客户类型') or '潜在客户',['潜在客户','正式客户','重点客户']))
        db().add(c);db().flush()
        if r.get('联系人'): db().add(Contact(customer_id=c.id,**contact_data({'name':r['联系人'],'email':r.get('邮箱','')})))
        audit('导入客户',c);added+=1
    return jsonify(added=added,skipped=skipped)


