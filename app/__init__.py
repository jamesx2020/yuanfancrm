from pathlib import Path
import secrets, logging
from datetime import timedelta
from flask import Flask, g, request, session, jsonify
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException, Forbidden, Unauthorized
from app.extensions import init_db, db
from app.models import User

def create_app(config=None):
    root=Path(__file__).resolve().parent.parent
    app=Flask(__name__,instance_path=str(root/'instance'))
    app.config.update(DATABASE_PATH=str(root/'instance'/'crm.sqlite3'),UPLOAD_PATH=str(root/'instance'/'uploads'),MAX_CONTENT_LENGTH=10*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    if config: app.config.update(config)
    Path(app.config['DATABASE_PATH']).parent.mkdir(parents=True,exist_ok=True)
    Path(app.config['UPLOAD_PATH']).mkdir(parents=True,exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        keyfile=Path(app.instance_path)/'secret.key'; keyfile.parent.mkdir(exist_ok=True)
        if not keyfile.exists():
            try:
                with keyfile.open('x') as f: f.write(secrets.token_hex(32))
                keyfile.chmod(0o600)
            except FileExistsError: pass
        app.config['SECRET_KEY']=keyfile.read_text()
    init_db(app)
    @app.before_request
    def protect():
        if request.path.startswith('/static/'): return
        g.user=None
        if request.method in ['POST','PUT','PATCH','DELETE']: db().execute(text('BEGIN IMMEDIATE'))
        if session.get('uid'):
            g.user=db().get(User,session['uid'])
            if not g.user or not g.user.active: session.clear();g.user=None
        if request.path.startswith('/api/') and request.path not in ['/api/auth/login','/api/auth/session'] and not g.user: raise Unauthorized('请先登录')
        if request.method in ['POST','PUT','PATCH','DELETE']:
            token=request.headers.get('X-CSRF-Token','')
            if not token or not secrets.compare_digest(token,session.get('csrf','')): raise Forbidden('会话校验失败，请刷新页面')
            if request.is_json and not isinstance(request.get_json(silent=True),dict):
                from werkzeug.exceptions import BadRequest
                raise BadRequest('请求必须为 JSON 对象')
    @app.after_request
    def complete(response):
        if 'db' in g:
            if request.method in ['POST','PUT','PATCH','DELETE'] and response.status_code<400: db().commit()
            else: db().rollback()
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        if request.path.startswith('/api/') or request.path=='/': response.headers['Cache-Control']='no-store'
        return response
    @app.errorhandler(HTTPException)
    def http_error(e):
        db().rollback();return jsonify(error=e.description),e.code
    @app.errorhandler(IntegrityError)
    def conflict(e):
        db().rollback();return jsonify(error='记录重复或关联数据不合法，请刷新后重试'),409
    @app.errorhandler(OperationalError)
    def locked(e):
        db().rollback();app.logger.exception('Database operation failed');return jsonify(error='数据库暂不可用，请稍后重试'),503
    @app.errorhandler(Exception)
    def failed(e):
        db().rollback();app.logger.exception('Unhandled error');return jsonify(error='操作失败，请查看本地运行日志'),500
    from app.modules.auth import bp as auth
    from app.modules.business import bp as business
    from app.modules.files import bp as files
    app.register_blueprint(auth);app.register_blueprint(business);app.register_blueprint(files)
    return app
