import secrets
from flask import Blueprint, request, session, jsonify, g, render_template
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest, Unauthorized
from app.extensions import db
from app.models import User
from app.services.serialization import user
from app.services.audit import audit
from app.utils import text
bp=Blueprint('auth',__name__)
@bp.get('/')
def index(): return render_template('index.html')
@bp.get('/api/auth/session')
def info():
    if 'csrf' not in session: session['csrf']=secrets.token_hex(32)
    return jsonify(csrf=session['csrf'],user=user(g.user) if g.user else None)
@bp.post('/api/auth/login')
def login():
    data=request.get_json();u=db().scalar(select(User).where(User.username==text(data,'username',True,80)))
    if not u or not u.active or not check_password_hash(u.password_hash,text(data,'password',True,500)): raise Unauthorized('账号或密码错误')
    session.clear();session['uid']=u.id;session['csrf']=secrets.token_hex(32);session.permanent=True;g.user=u;audit('登录',u)
    return jsonify(user=user(u),csrf=session['csrf'])
@bp.post('/api/auth/logout')
def logout(): session.clear();return jsonify(ok=True)
@bp.post('/api/auth/password')
def password():
    d=request.get_json()
    if not check_password_hash(g.user.password_hash,text(d,'old_password',True,500)): raise BadRequest('原密码错误')
    new=text(d,'password',True,500)
    if len(new)<10: raise BadRequest('新密码至少 10 位')
    g.user.password_hash=generate_password_hash(new);audit('修改密码',g.user);return jsonify(ok=True)
