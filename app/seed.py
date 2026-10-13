from datetime import date,timedelta
from flask import g
from sqlalchemy import select
from app.extensions import db
from app.models import *
from app.services.quotation import create_quote,convert
from app.utils import today

def seed():
    admin=db().scalar(select(User).where(User.role=='admin',User.active==True))
    if not admin: raise ValueError('请先初始化管理员')
    if db().scalar(select(Customer.id).where(Customer.source=='示例数据')): return
    g.user=admin;now=date.fromisoformat(today())
    products=[]
    for sku,name,spec,mode,cost in [('DEMO-OF-001','柚木户外休闲椅','FSC 柚木 · 62 × 58 × 78 cm','自产',5200),('DEMO-KT-008','陶瓷餐具套装','哑光釉面 · 4 件套','外采',1100),('DEMO-LT-003','简约金属吊灯','铝制灯罩 · E27','混合供货',2500)]:
        p=Product(sku=sku,name=name,spec=spec,mode=mode,cost=cost);db().add(p);db().flush();products.append(p)
    supplier=Supplier(name='示例 · 景德镇优选陶瓷',contact='张先生');db().add(supplier);db().flush()
    db().add(ProductSource(product_id=products[0].id,mode='自产',cost=5200));db().add(ProductSource(product_id=products[1].id,mode='外采',supplier_id=supplier.id,cost=1100))
    data=[('Nordic Living GmbH','德国','Anna Müller','重点客户','户外家具'),('Pacific Home Inc.','美国','James Wilson','正式客户','家居用品'),('Sakura Trading Co.','日本','Yuki Tanaka','潜在客户','陶瓷餐具'),('Coastal Interiors Ltd.','英国','Oliver Smith','正式客户','装饰灯具')]
    customers=[]
    for i,(name,country,person,level,product) in enumerate(data):
        c=Customer(name=name,name_key=name.casefold(),country=country,source='示例数据',level=level,product=product,owner_id=admin.id);db().add(c);db().flush();customers.append(c)
        db().add(Contact(customer_id=c.id,name=person,email=f'contact{i}@example.com'))
        db().add(Task(customer_id=c.id,user_id=admin.id,title=['确认包装方案','核实生产交期','发送产品报价','确认出货资料'][i],due_date=(now+timedelta(days=i-1)).isoformat()))
        db().add(Followup(customer_id=c.id,user_id=admin.id,content='这是可编辑的示例记录。客户已收到产品资料，等待进一步确认需求。',channel='邮件'))
        db().add(Opportunity(customer_id=c.id,title=product+'采购项目',stage=['样品 / 谈判','待确认订单','需求确认','已报价'][i],amount=[4300000,2860000,1440000,1260000][i],next_action='确认规格与交期'))
    q=create_quote({'customer_id':customers[0].id,'valid_until':(now+timedelta(days=14)).isoformat(),'term':'FOB Ningbo','payment_terms':'30% 定金，70% 出货前','lead_time':'收到定金后 30 天','lines':[{'product_id':products[0].id,'name':products[0].name,'spec':products[0].spec,'quantity':500,'price':'86','unit':'把'}]});q.status='待确认'
    q2=create_quote({'customer_id':customers[1].id,'valid_until':(now+timedelta(days=14)).isoformat(),'term':'FOB Ningbo','payment_terms':'30% 定金，70% 出货前','lead_time':'收到定金后 30 天','lines':[{'product_id':products[0].id,'name':products[0].name,'spec':products[0].spec,'quantity':200,'price':'86','unit':'把'},{'product_id':products[2].id,'name':products[2].name,'quantity':300,'price':'38','unit':'盏'}]})
    o=convert(q2,(now+timedelta(days=20)).isoformat());db().flush()
    lines=db().scalars(select(OrderLine).where(OrderLine.order_id==o.id)).all()
    for l in lines: db().add(SupplyTask(order_line_id=l.id,mode='自产',assignee_id=admin.id,quantity=l.quantity,cost=2500,due_date=o.due_date,progress=65))
    db().add(Payment(order_id=o.id,amount=858000,paid_date=today(),note='示例定金',user_id=admin.id,request_key='demo-initial-payment'));o.status='供货执行中'
