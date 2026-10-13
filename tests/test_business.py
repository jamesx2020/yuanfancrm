from io import BytesIO
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Order,QuoteLine,Audit,Customer,User

def convert(b):
    r=b['req']('POST',f"/quotations/{b['quote']['id']}/convert",{'due_date':'2026-12-31'})
    assert r.status_code==200,r.json
    return r.json

def test_login_csrf_and_logout(app,login):
    c=app.test_client();assert c.get('/api/bootstrap').status_code==401
    assert c.post('/api/auth/login',json={'username':'admin','password':'Test-password-123'}).status_code==403
    c,req,_=login();assert c.get('/api/bootstrap').status_code==200
    req('POST','/auth/logout');assert c.get('/api/bootstrap').status_code==401

def test_sales_scope_and_no_cost_leak(business,login):
    _,other,_=login('other')
    assert other('GET','/customers/'+str(business['customer']['id'])).status_code==403
    assert other('GET','/bootstrap').json['customers']==[]
    assert other('POST','/quotations/'+str(business['quote']['id'])+'/copy').status_code==403
    _,sales,_=login('sales')
    assert sales('POST','/products',{'sku':'SKU','name':'x'}).status_code==403
    assert sales('GET','/users').status_code==403

def test_duplicate_customer_does_not_leave_contact(business):
    r=business['req']('POST','/customers',{'name':'test CUSTOMER','country':'UK','contacts':[{'name':'Ghost'}]})
    assert r.status_code==409
    assert len(business['req']('GET','/bootstrap').json['customers'])==1

def test_followup_creates_task_and_reassigns_with_customer(business,login):
    b=business;req=b['req'];cid=b['customer']['id']
    r=req('POST',f'/customers/{cid}/followups',{'content':'Discussed details','next_action':'Call Anna','due_date':'2026-12-10'})
    assert r.status_code==201
    assert req('GET','/bootstrap').json['tasks'][0]['title']=='Call Anna'
    _,admin,_=login();other=next(u for u in admin('GET','/users').json if u['username']=='other')
    assert admin('PATCH',f'/customers/{cid}',{'owner_id':other['id']}).status_code==200
    assert req('GET','/bootstrap').json['tasks']==[]
    _,new,_=login('other');assert new('GET','/bootstrap').json['tasks'][0]['title']=='Call Anna'

def test_quote_money_snapshot_and_idempotent_conversion(business,app):
    b=business;q=b['quote'];assert q['amount']==22340
    first=convert(b);second=convert(b);assert first['id']==second['id']
    assert first['amount']==22340 and len(first['lines'])==2
    r=b['req']('PATCH',f"/quotations/{q['id']}",{'status':'草稿'})
    assert r.status_code==400
    with Session(app.extensions['engine']) as s:
        assert len(s.scalars(select(Order)).all())==1
        assert len(s.scalars(select(Audit).where(Audit.action=='报价转订单')).all())==1

def test_quote_versions_edit_does_not_change_original(business):
    b=business;req=b['req'];q=b['quote']
    n=req('POST',f"/quotations/{q['id']}/copy").json
    assert n['version']==2
    data=b['quote_data'].copy();data['lines']=[{'name':'Revised Chair','quantity':2,'price':'9.99'}]
    assert req('PATCH',f"/quotations/{n['id']}",data).status_code==200
    bootstrap=req('GET','/bootstrap').json
    assert next(x for x in bootstrap['quotes'] if x['id']==q['id'])['amount']==22340
    assert next(x for x in bootstrap['quotes'] if x['id']==n['id'])['amount']==1998

def test_invalid_lines_roll_back_whole_quote(business,app):
    data={**business['quote_data'],'lines':[{'name':'Good','quantity':1,'price':'2'},{'name':'Bad','quantity':1,'price':'0.001'}]}
    r=business['req']('POST','/quotations',data);assert r.status_code==400
    assert len(business['req']('GET','/bootstrap').json['quotes'])==1

def test_partial_payment_idempotency_void_and_overpayment(business,login):
    o=convert(business);_,fin,_=login('finance');path=f"/orders/{o['id']}/payments"
    d={'amount':'100','paid_date':'2026-10-13','request_key':'payment-one'}
    r=fin('POST',path,d);assert r.status_code==201,r.json
    duplicate=fin('POST',path,d);assert duplicate.json['id']==r.json['id']
    assert fin('GET','/bootstrap').json['orders'][0]['balance']==12340
    assert fin('POST',path,{**d,'amount':'124','request_key':'too-much'}).status_code==400
    assert business['req']('POST',path,{**d,'request_key':'sales-attempt'}).status_code==403
    assert fin('POST',f"/payments/{r.json['id']}/void",{'reason':'Wrong bank entry'}).status_code==200
    assert fin('GET','/bootstrap').json['orders'][0]['balance']==22340
    assert fin('POST',f"/payments/{r.json['id']}/void",{'reason':'Again'}).status_code==400

def test_partial_shipments_and_quantity_limits(business):
    b=business;o=convert(b);req=b['req'];path=f"/orders/{o['id']}/shipments";lid=o['lines'][0]['id']
    d={'tracking':'BL-001','ship_date':'2026-10-13','request_key':'shipment-one','lines':[{'order_line_id':lid,'quantity':4}]}
    r=req('POST',path,d);assert r.status_code==201,r.json
    assert req('POST',path,d).json['id']==r.json['id']
    assert req('GET','/bootstrap').json['orders'][0]['shipped']==4
    assert req('POST',path,{**d,'request_key':'too-many','lines':[{'order_line_id':lid,'quantity':7}]}).status_code==400
    assert req('GET','/bootstrap').json['orders'][0]['shipped']==4

def test_supply_allocations_and_procurement_permissions(business,login):
    o=convert(business);_,admin,_=login();users=admin('GET','/users').json;buyer=next(u for u in users if u['username']=='buyer')
    data={'order_line_id':o['lines'][0]['id'],'mode':'自产','quantity':6,'assignee_id':buyer['id'],'due_date':'2026-12-10','cost':'5'}
    r=admin('POST',f"/orders/{o['id']}/supply",data);assert r.status_code==201,r.json
    assert admin('POST',f"/orders/{o['id']}/supply",{**data,'quantity':5}).status_code==400
    _,proc,_=login('buyer');s=proc('GET','/bootstrap').json
    assert len(s['orders'])==1 and 'amount' not in s['orders'][0]
    assert 'price' not in s['orders'][0]['lines'][0]
    assert proc('PATCH',f"/supply/{r.json['id']}",{'progress':80,'quality':'OK'}).status_code==200
    assert proc('POST',f"/orders/{o['id']}/payments",{'amount':1}).status_code==403
    assert proc('GET',f"/attachments/orders/{o['id']}").status_code==403
    assert proc('GET',f"/customers/{business['customer']['id']}").status_code==403

def test_attachment_download_permissions_and_pdf(business,login):
    b=business;cid=b['customer']['id'];c=b['client']
    r=c.post(f'/api/attachments/customers/{cid}',data={'file':(BytesIO(b'hello'),'note.txt')},headers={'X-CSRF-Token':b['token']})
    assert r.status_code==201,r.json
    id=r.json['id'];assert c.get(f'/api/attachments/{id}/download').data==b'hello'
    other,_,_=login('other');assert other.get(f'/api/attachments/{id}/download').status_code==403
    r=c.get(f"/api/quotations/{b['quote']['id']}/pdf");assert r.status_code==200 and r.data.startswith(b'%PDF')
    r=c.post(f'/api/attachments/customers/{cid}',data={'file':(BytesIO(b'<script>'),'bad.html')},headers={'X-CSRF-Token':b['token']})
    assert r.status_code==400

def test_csv_import_atomic_and_formula_safe(login):
    c,req,token=login('sales')
    good='公司名称,国家,联系人,邮箱\n=SUM(A1),德国,Anna,anna@example.com\n'
    r=c.post('/api/customers/import',data={'file':(BytesIO(good.encode()),'data.csv')},headers={'X-CSRF-Token':token});assert r.status_code==200,r.json
    exported=c.get('/api/customers/export').data.decode('utf-8-sig');assert "'=SUM(A1)" in exported
    bad='公司名称,国家,联系人,邮箱\nValid,UK,A,a@example.com\n,UK,B,b@example.com\n'
    r=c.post('/api/customers/import',data={'file':(BytesIO(bad.encode()),'data.csv')},headers={'X-CSRF-Token':token});assert r.status_code==400
    assert len(req('GET','/bootstrap').json['customers'])==1

def test_reports_separate_currencies_and_persistence(business,app,login):
    b=business;convert(b);data={**b['quote_data'],'currency':'EUR'}
    q=b['req']('POST','/quotations',data).json
    b['req']('POST',f"/quotations/{q['id']}/convert",{'due_date':'2026-12-31'})
    r=b['req']('GET','/reports').json
    assert r['by_currency']['USD']['amount']==22340
    assert r['by_currency']['EUR']['amount']==22340
    with Session(app.extensions['engine']) as s: assert len(s.scalars(select(Order)).all())==2
    new_app=__import__('app').create_app({**app.config,'SECRET_KEY':'test-only-key'})
    c=new_app.test_client();token=c.get('/api/auth/session').json['csrf'];r=c.post('/api/auth/login',json={'username':'sales','password':'Test-password-123'},headers={'X-CSRF-Token':token});assert r.status_code==200
    assert len(c.get('/api/bootstrap').json['orders'])==2
    new_app.extensions['engine'].dispose()

def test_disabled_user_is_logged_out_and_password_change(login):
    c,req,_=login('sales');assert req('POST','/auth/password',{'old_password':'wrong','password':'new-password-123'}).status_code==400
    _,admin,_=login();u=next(u for u in admin('GET','/users').json if u['username']=='sales')
    assert admin('PATCH',f"/users/{u['id']}",{'active':False}).status_code==200
    assert c.get('/api/bootstrap').status_code==401

def test_concurrent_payments_cannot_overdraw(business,login):
    from concurrent.futures import ThreadPoolExecutor
    o=convert(business)
    _,fin1,_=login('finance');_,fin2,_=login('finance')
    path=f"/orders/{o['id']}/payments"
    def pay(pair):
        req,key=pair
        return req('POST',path,{'amount':'150','paid_date':'2026-10-13','request_key':key}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=sorted(pool.map(pay,[(fin1,'race-1'),(fin2,'race-2')]))
    assert codes==[201,400]
    assert fin1('GET','/bootstrap').json['orders'][0]['balance']==7340

def test_fresh_alembic_migration(tmp_path,monkeypatch):
    import app as app_module
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect
    from app.models import Base
    fresh=app_module.create_app({'SECRET_KEY':'migration-test','DATABASE_PATH':str(tmp_path/'fresh.sqlite3'),'UPLOAD_PATH':str(tmp_path/'uploads')})
    monkeypatch.setattr(app_module,'create_app',lambda:fresh)
    config=Config('alembic.ini');command.upgrade(config,'head')
    assert set(inspect(fresh.extensions['engine']).get_table_names())==set(Base.metadata.tables)|{'alembic_version'}
    command.downgrade(config,'base');command.upgrade(config,'head')
    assert 'orders' in inspect(fresh.extensions['engine']).get_table_names()
    fresh.extensions['engine'].dispose()

def test_product_image_validation_and_preview(login):
    from PIL import Image
    c,req,token=login()
    p=req('POST','/products',{'sku':'IMAGE-SKU','name':'Image Product'}).json
    path=f"/api/attachments/products/{p['id']}"
    bad=c.post(path,data={'file':(BytesIO(b'not an image'),'fake.png')},headers={'X-CSRF-Token':token})
    assert bad.status_code==400
    content=BytesIO();Image.new('RGB',(10,10),'white').save(content,format='PNG');content.seek(0)
    r=c.post(path,data={'file':(content,'product.png')},headers={'X-CSRF-Token':token});assert r.status_code==201,r.json
    assert c.get(f"/api/attachments/{r.json['id']}/preview").status_code==200
    assert req('GET','/bootstrap').json['products'][0]['image_id']==r.json['id']
