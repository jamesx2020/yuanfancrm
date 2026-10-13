import json
from flask import g
from app.extensions import db
from app.models import Audit

def audit(action,obj,details=None):
    db().flush()
    db().add(Audit(user_id=g.user.id,action=action,entity=obj.__tablename__,entity_id=obj.id,details=json.dumps(details or {},ensure_ascii=False)))
