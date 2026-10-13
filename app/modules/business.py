from flask import Blueprint
from app.modules import dashboard,customers,products,quotations,orders,finance,settings
bp=Blueprint('business',__name__)
for module in [dashboard,customers,products,quotations,orders,finance,settings]:
    bp.register_blueprint(module.bp)
