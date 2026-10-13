"""Local CRM entry point. See README.md for first-run setup."""
import argparse
import getpass
import secrets
import sqlite3
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User
ROOT=Path(__file__).resolve().parent

def upgrade():
    from alembic.config import Config
    from alembic import command
    c=Config(str(ROOT/'alembic.ini'));command.upgrade(c,'head')

def main():
    parser=argparse.ArgumentParser(description='远帆 CRM · 本地部署')
    subs=parser.add_subparsers(dest='cmd')
    init=subs.add_parser('init',help='初始化数据库并创建管理员');init.add_argument('--username',default='admin');init.add_argument('--name',default='管理员')
    subs.add_parser('upgrade',help='升级数据库结构')
    subs.add_parser('seed',help='添加可选示例业务数据（幂等）')
    subs.add_parser('backup',help='备份数据库及附件')
    restore=subs.add_parser('restore',help='恢复备份，须先停止服务');restore.add_argument('archive')
    reset=subs.add_parser('reset-password',help='本机重置账号密码');reset.add_argument('username')
    serve=subs.add_parser('serve',help='启动本地服务');serve.add_argument('--port',type=int,default=5001)
    args=parser.parse_args();cmd=args.cmd or 'serve'
    if cmd=='upgrade': upgrade();print('数据库已升级');return
    if cmd=='init':
        upgrade();app=create_app()
        with app.app_context():
            if db().scalar(select(User).where(User.username==args.username)): print('账号已存在，不做修改。');return
            password=getpass.getpass('管理员密码（至少 10 位，留空自动生成）：')
            generated=not password
            if generated: password=secrets.token_urlsafe(15)
            if len(password)<10: parser.error('密码至少 10 位')
            db().add(User(username=args.username,name=args.name,role='admin',password_hash=generate_password_hash(password)));db().commit()
            print('管理员已创建，账号：'+args.username)
            if generated: print('自动生成的初始密码：'+password+'\n请保存并在登录后修改。')
        return
    if cmd=='seed':
        upgrade();from app.seed import seed
        app=create_app()
        with app.app_context(): seed();db().commit()
        print('示例数据已添加；不会覆盖已有业务数据。');return
    if cmd=='backup':
        app=create_app();stamp=datetime.now().strftime('%Y%m%d-%H%M%S');dest=ROOT/'backups'/('crm-'+stamp);dest.mkdir(parents=True,exist_ok=False)
        source=sqlite3.connect(app.config['DATABASE_PATH']);target=sqlite3.connect(dest/'crm.sqlite3');source.backup(target);target.close();source.close()
        with sqlite3.connect(dest/'crm.sqlite3') as snap: attachments=snap.execute('SELECT storage_name FROM attachments').fetchall()
        (dest/'uploads').mkdir()
        for (name,) in attachments:
            shutil.copy2(Path(app.config['UPLOAD_PATH'])/name,dest/'uploads'/name)
        (dest/'manifest.json').write_text(json.dumps({'format':1,'created_at':stamp,'database':'crm.sqlite3','attachments':len(attachments)}))
        archive=shutil.make_archive(str(dest),'zip',dest);shutil.rmtree(dest);print('备份完成：'+archive);return
    if cmd=='restore':
        if input('请先停止 CRM 服务。恢复会替换现有数据库，输入 RESTORE 确认：')!='RESTORE': print('已取消');return
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            with zipfile.ZipFile(args.archive) as z:
                for info in z.infolist():
                    path=(base/info.filename).resolve()
                    if not path.is_relative_to(base.resolve()) or (info.external_attr>>16)&0o170000==0o120000: parser.error('备份包含不安全路径')
                if sum(i.file_size for i in z.infolist())>2*1024**3: parser.error('备份超过 2 GB')
                z.extractall(base)
            if not (base/'crm.sqlite3').exists() or not (base/'manifest.json').exists(): parser.error('不是有效 CRM 备份')
            try:
                manifest=json.loads((base/'manifest.json').read_text())
                if manifest.get('format')!=1: parser.error('不支持的备份格式')
                with sqlite3.connect(base/'crm.sqlite3') as c:
                    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok': parser.error('数据库校验失败')
                    if c.execute('PRAGMA foreign_key_check').fetchone(): parser.error('备份存在失效关联')
                    names=[r[0] for r in c.execute('SELECT storage_name FROM attachments')]
                    if not c.execute('SELECT id FROM users LIMIT 1').fetchone(): parser.error('备份缺少用户数据')
                if len(names)!=manifest.get('attachments'): parser.error('备份附件清单不一致')
                if not (base/'uploads').is_dir(): parser.error('备份缺少附件目录')
                for name in names:
                    if Path(name).name!=name or not (base/'uploads'/name).is_file(): parser.error('备份附件缺失或路径不合法')
            except (sqlite3.Error,ValueError,OSError) as e: parser.error('备份校验失败：'+str(e))
            target=ROOT/'instance';target.mkdir(exist_ok=True)
            # Preserve current instance before replacement.
            if (target/'crm.sqlite3').exists():
                safety=ROOT/'backups'/('before-restore-'+datetime.now().strftime('%Y%m%d-%H%M%S'));shutil.copytree(target,safety)
                print('恢复前副本：'+str(safety))
            for suffix in ['-wal','-shm']:
                (target/('crm.sqlite3'+suffix)).unlink(missing_ok=True)
            shutil.copy2(base/'crm.sqlite3',target/'crm.sqlite3')
            shutil.copytree(base/'uploads',target/'uploads',dirs_exist_ok=True)
            (target/'secret.key').write_text(secrets.token_hex(32));(target/'secret.key').chmod(0o600)
        print('恢复完成。原会话已失效，请重启并重新登录。');return
    app=create_app()
    if cmd=='reset-password':
        with app.app_context():
            u=db().scalar(select(User).where(User.username==args.username))
            if not u: parser.error('用户不存在')
            password=getpass.getpass('新密码（至少 10 位）：')
            if len(password)<10: parser.error('密码至少 10 位')
            u.password_hash=generate_password_hash(password);db().commit();print('密码已更新')
        return
    with app.app_context():
        try: ready=db().scalar(select(User.id).limit(1))
        except Exception: ready=None
        if not ready: parser.error('请先运行 .venv/bin/python run.py init')
    from waitress import serve
    port=getattr(args,'port',5001)
    print(f'远帆 CRM 已启动：http://127.0.0.1:{port}\n按 Ctrl+C 停止。',flush=True)
    serve(app,host='127.0.0.1',port=port,threads=4)
if __name__=='__main__': main()
