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
bp=Blueprint('settings',__name__)

@bp.get('/api/users')
def users():
    role('admin');return jsonify([ser.user(u) for u in db().scalars(select(User).order_by(User.id))])


@bp.post('/api/users')
def user_create():
    role('admin');d=request.get_json();password=text(d,'password',True,500)
    if len(password)<10: raise BadRequest('密码至少 10 位')
    u=User(username=text(d,'username',True,80),name=text(d,'name',True,80),role=choice(d.get('role'),['admin','sales','procurement','finance']),password_hash=generate_password_hash(password));db().add(u);audit('创建用户',u);return jsonify(ser.user(u)),201


@bp.patch('/api/users/<int:id>')
def user_update(id):
    role('admin');u=get(User,id);d=request.get_json()
    if id==g.user.id and ('active' in d or 'role' in d): raise BadRequest('不能停用自己或修改自己的角色')
    if 'active' in d:
        if not isinstance(d['active'],bool): raise BadRequest('启用值必须为布尔值')
        u.active=d['active']
    if 'password' in d:
        password=text(d,'password',True,500)
        if len(password)<10: raise BadRequest('密码至少 10 位')
        u.password_hash=generate_password_hash(password)
    audit('更新账号',u,{'fields':[k for k in d if k!='password']});return jsonify(ser.user(u))


@bp.get('/api/audit')
def audit_list():
    role('admin');return jsonify([{**ser.base(a),'user':get(User,a.user_id).name} for a in db().scalars(select(Audit).order_by(Audit.id.desc()).limit(100))])


