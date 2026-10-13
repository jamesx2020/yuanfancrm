from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()
def timestamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
class Common:
    id = Column(Integer, primary_key=True)
    created_at = Column(String(40), default=timestamp, nullable=False)
class User(Common, Base):
    __tablename__='users'
    username=Column(String(80),unique=True,nullable=False)
    name=Column(String(80),nullable=False)
    password_hash=Column(Text,nullable=False)
    role=Column(String(30),nullable=False,default='sales')
    active=Column(Boolean,default=True,nullable=False)
class Customer(Common,Base):
    __tablename__='customers'
    name=Column(String(200),nullable=False)
    name_key=Column(String(200),unique=True,nullable=False)
    country=Column(String(80),default='')
    website=Column(String(300),default='')
    source=Column(String(80),default='')
    level=Column(String(30),default='潜在客户')
    product=Column(String(200),default='')
    owner_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    archived=Column(Boolean,default=False,nullable=False)
class Contact(Common,Base):
    __tablename__='contacts'
    customer_id=Column(Integer,ForeignKey('customers.id'),nullable=False,index=True)
    name=Column(String(100),nullable=False)
    email=Column(String(200),default='')
    phone=Column(String(80),default='')
    position=Column(String(80),default='')
class Followup(Common,Base):
    __tablename__='followups'
    customer_id=Column(Integer,ForeignKey('customers.id'),nullable=False,index=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    content=Column(Text,nullable=False)
    channel=Column(String(30),default='邮件')
class Task(Common,Base):
    __tablename__='tasks'
    customer_id=Column(Integer,ForeignKey('customers.id'))
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    title=Column(String(300),nullable=False)
    due_date=Column(String(10),nullable=False)
    done=Column(Boolean,default=False,nullable=False)
class Opportunity(Common,Base):
    __tablename__='opportunities'
    customer_id=Column(Integer,ForeignKey('customers.id'),nullable=False)
    title=Column(String(200),nullable=False)
    stage=Column(String(40),default='新询盘',nullable=False)
    amount=Column(Integer,default=0,nullable=False)
    currency=Column(String(3),default='USD')
    next_action=Column(String(300),default='')
    expected_date=Column(String(10),default='')
    loss_reason=Column(Text,default='')
class Supplier(Common,Base):
    __tablename__='suppliers'
    name=Column(String(200),nullable=False,unique=True)
    contact=Column(String(200),default='')
    phone=Column(String(80),default='')
class Product(Common,Base):
    __tablename__='products'
    sku=Column(String(80),unique=True,nullable=False)
    name=Column(String(200),nullable=False)
    spec=Column(Text,default='')
    unit=Column(String(30),default='件')
    mode=Column(String(30),default='自产')
    cost=Column(Integer,default=0)
    currency=Column(String(3),default='USD')
    archived=Column(Boolean,default=False,nullable=False)
class ProductSource(Common,Base):
    __tablename__='product_sources'
    product_id=Column(Integer,ForeignKey('products.id'),nullable=False)
    supplier_id=Column(Integer,ForeignKey('suppliers.id'))
    mode=Column(String(30),nullable=False)
    cost=Column(Integer,default=0)
    __table_args__=(UniqueConstraint('product_id','supplier_id','mode'),)
class Quotation(Common,Base):
    __tablename__='quotations'
    customer_id=Column(Integer,ForeignKey('customers.id'),nullable=False)
    opportunity_id=Column(Integer,ForeignKey('opportunities.id'))
    number=Column(String(80),unique=True,nullable=False)
    root_id=Column(Integer,ForeignKey('quotations.id'))
    version=Column(Integer,default=1,nullable=False)
    currency=Column(String(3),default='USD',nullable=False)
    status=Column(String(30),default='草稿',nullable=False)
    valid_until=Column(String(10),nullable=False)
    term=Column(String(200),default='FOB Ningbo')
    payment_terms=Column(String(300),default='30% deposit, 70% before shipment')
    lead_time=Column(String(200),default='30 days after deposit')
    notes=Column(Text,default='')
    __table_args__=(UniqueConstraint('root_id','version'),)
class QuoteLine(Common,Base):
    __tablename__='quotation_lines'
    quotation_id=Column(Integer,ForeignKey('quotations.id'),nullable=False,index=True)
    product_id=Column(Integer,ForeignKey('products.id'))
    name=Column(String(200),nullable=False)
    spec=Column(Text,default='')
    unit=Column(String(30),default='件')
    quantity=Column(Integer,nullable=False)
    price=Column(Integer,nullable=False)
    __table_args__=(CheckConstraint('quantity > 0'),CheckConstraint('price >= 0'))
class Order(Common,Base):
    __tablename__='orders'
    quotation_id=Column(Integer,ForeignKey('quotations.id'),unique=True,nullable=False)
    customer_id=Column(Integer,ForeignKey('customers.id'),nullable=False)
    number=Column(String(80),unique=True,nullable=False)
    currency=Column(String(3),nullable=False)
    term=Column(String(200),default='')
    payment_terms=Column(String(300),default='')
    lead_time=Column(String(200),default='')
    due_date=Column(String(10),default='')
    status=Column(String(30),default='待安排供货')
class OrderLine(Common,Base):
    __tablename__='order_lines'
    order_id=Column(Integer,ForeignKey('orders.id'),nullable=False,index=True)
    product_id=Column(Integer,ForeignKey('products.id'))
    name=Column(String(200),nullable=False)
    spec=Column(Text,default='')
    unit=Column(String(30),default='件')
    quantity=Column(Integer,nullable=False)
    price=Column(Integer,nullable=False)
    __table_args__=(CheckConstraint('quantity > 0'),CheckConstraint('price >= 0'))
class SupplyTask(Common,Base):
    __tablename__='supply_tasks'
    order_line_id=Column(Integer,ForeignKey('order_lines.id'),nullable=False,index=True)
    mode=Column(String(30),nullable=False)
    supplier_id=Column(Integer,ForeignKey('suppliers.id'))
    assignee_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    quantity=Column(Integer,nullable=False)
    cost=Column(Integer,default=0)
    due_date=Column(String(10),nullable=False)
    progress=Column(Integer,default=0,nullable=False)
    quality=Column(String(200),default='待检')
    __table_args__=(CheckConstraint('quantity > 0'),CheckConstraint('progress >= 0 AND progress <= 100'))
class Payment(Common,Base):
    __tablename__='payments'
    order_id=Column(Integer,ForeignKey('orders.id'),nullable=False,index=True)
    amount=Column(Integer,nullable=False)
    paid_date=Column(String(10),nullable=False)
    note=Column(Text,default='')
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    request_key=Column(String(80),unique=True,nullable=False)
    voided=Column(Boolean,default=False,nullable=False)
    void_reason=Column(Text,default='')
    __table_args__=(CheckConstraint('amount > 0'),)
class Shipment(Common,Base):
    __tablename__='shipments'
    order_id=Column(Integer,ForeignKey('orders.id'),nullable=False,index=True)
    tracking=Column(String(200),nullable=False)
    ship_date=Column(String(10),nullable=False)
    destination=Column(String(200),default='')
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    request_key=Column(String(80),unique=True,nullable=False)
class ShipmentLine(Common,Base):
    __tablename__='shipment_lines'
    shipment_id=Column(Integer,ForeignKey('shipments.id'),nullable=False)
    order_line_id=Column(Integer,ForeignKey('order_lines.id'),nullable=False)
    quantity=Column(Integer,nullable=False)
    __table_args__=(CheckConstraint('quantity > 0'),UniqueConstraint('shipment_id','order_line_id'))
class Attachment(Common,Base):
    __tablename__='attachments'
    entity=Column(String(30),nullable=False)
    entity_id=Column(Integer,nullable=False)
    filename=Column(String(250),nullable=False)
    storage_name=Column(String(80),unique=True,nullable=False)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
class Audit(Common,Base):
    __tablename__='audit_logs'
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    action=Column(String(100),nullable=False)
    entity=Column(String(30),nullable=False)
    entity_id=Column(Integer,nullable=False)
    details=Column(Text,default='')
