import pytest
from werkzeug.security import generate_password_hash
from sqlalchemy.orm import Session
from app import create_app
from app.models import Base, User

@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SECRET_KEY':'test-only-key','DATABASE_PATH':str(tmp_path/'test.sqlite3'),'UPLOAD_PATH':str(tmp_path/'uploads')})
    Base.metadata.create_all(app.extensions['engine'])
    with Session(app.extensions['engine']) as s:
        for username,role in [('admin','admin'),('sales','sales'),('other','sales'),('finance','finance'),('buyer','procurement')]:
            s.add(User(username=username,name=username,role=role,password_hash=generate_password_hash('Test-password-123')))
        s.commit()
    yield app
    app.extensions['engine'].dispose()

@pytest.fixture
def login(app):
    def factory(username='admin'):
        client=app.test_client();csrf=client.get('/api/auth/session').json['csrf']
        r=client.post('/api/auth/login',json={'username':username,'password':'Test-password-123'},headers={'X-CSRF-Token':csrf})
        assert r.status_code==200,r.json
        token=r.json['csrf']
        def request(method,path,data=None):
            return client.open('/api'+path,method=method,json=data or {},headers={'X-CSRF-Token':token})
        return client,request,token
    return factory

@pytest.fixture
def business(login):
    c,req,token=login('sales')
    r=req('POST','/customers',{'name':'Test Customer','country':'Germany','contacts':[{'name':'Anna','email':'anna@example.com'}]});assert r.status_code==201
    customer=r.json
    data={'customer_id':customer['id'],'currency':'USD','valid_until':'2026-12-31','term':'FOB Ningbo','payment_terms':'30% deposit','lead_time':'30 days','lines':[{'name':'Chair','spec':'Teak','quantity':10,'price':'12.34','unit':'piece'},{'name':'Lamp','quantity':5,'price':'20','unit':'piece'}]}
    r=req('POST','/quotations',data);assert r.status_code==201,r.json
    return {'client':c,'req':req,'token':token,'customer':customer,'quote':r.json,'quote_data':data}
