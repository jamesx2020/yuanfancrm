import builtins
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Customer, Attachment

def test_backup_and_restore_round_trip(app,login,tmp_path,monkeypatch):
    import run
    _,req,_=login()
    c=req('POST','/customers',{'name':'Backup Customer','country':'CN'}).json
    uploads=Path(app.config['UPLOAD_PATH']);(uploads/'test.txt').write_text('attachment data')
    with Session(app.extensions['engine']) as s:
        s.add(Attachment(entity='customers',entity_id=c['id'],filename='original.txt',storage_name='test.txt',user_id=1));s.commit()
    monkeypatch.setattr(run,'ROOT',tmp_path);monkeypatch.setattr(run,'create_app',lambda:app)
    monkeypatch.setattr(sys,'argv',['run.py','backup']);run.main()
    archive=next((tmp_path/'backups').glob('crm-*.zip'))
    with zipfile.ZipFile(archive) as z:
        assert z.read('uploads/test.txt')==b'attachment data'
        assert json.loads(z.read('manifest.json'))['attachments']==1
    monkeypatch.setattr(sys,'argv',['run.py','restore',str(archive)])
    monkeypatch.setattr(builtins,'input',lambda _: 'RESTORE');run.main()
    restored=tmp_path/'instance'/'crm.sqlite3'
    with sqlite3.connect(restored) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('SELECT name FROM customers').fetchone()[0]=='Backup Customer'
    assert (tmp_path/'instance'/'uploads'/'test.txt').read_text()=='attachment data'
