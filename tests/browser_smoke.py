"""Optional UI check against an isolated temporary database, never real user data."""
import sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import Base,User
from app.extensions import db
from app.seed import seed
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def check():
    with tempfile.TemporaryDirectory() as temp:
        app=create_app({'SECRET_KEY':'ui-test-key','DATABASE_PATH':str(Path(temp)/'ui.sqlite3'),'UPLOAD_PATH':str(Path(temp)/'uploads')})
        Base.metadata.create_all(app.extensions['engine'])
        with app.app_context():
            db().add(User(username='admin',name='林晓',role='admin',password_hash=generate_password_hash('Browser-test-123')));db().commit();seed();db().commit()
        server=make_server('127.0.0.1',5012,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                executable='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                browser=p.chromium.launch(executable_path=executable if Path(executable).exists() else None,headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:5012');page.locator('[name=username]').fill('admin');page.locator('[name=password]').fill('Browser-test-123');page.locator('#loginForm button').click()
                page.locator('h1').filter(has_text='你好').wait_for()
                page.screenshot(path=str(ROOT/'screenshots'/'01-dashboard.png'),full_page=True)
                page.get_by_role('button',name='新建客户').click()
                for name,value in {'name':'Browser QA Client','country':'德国','contact_name':'Test Anna','email':'qa@example.com'}.items():page.locator('dialog [name='+name+']').fill(value)
                submit(page)
                page.get_by_role('button',name='Browser QA Client',exact=True).click();page.get_by_role('button',name='记录跟进').click()
                page.locator('dialog [name=content]').fill('确认 2 款产品需求，安排报价。');page.locator('dialog [name=next_action]').fill('追踪报价反馈');submit(page)
                page.get_by_role('button',name='添加',exact=False).filter(has_text='添加').first.click()
                page.locator('dialog [name=name]').fill('采购经理 Bob');page.locator('dialog [name=email]').fill('bob@example.com');submit(page)
                page.screenshot(path=str(ROOT/'screenshots'/'02-customer.png'),full_page=True)
                page.get_by_role('button',name='新建报价',exact=True).click()
                rows=page.locator('.quote-row');rows.nth(0).locator('[data-key=name]').fill('QA Chair');rows.nth(0).locator('[data-key=quantity]').fill('10');rows.nth(0).locator('[data-key=price]').fill('12.34')
                page.get_by_role('button',name='添加产品').click();rows.nth(1).locator('[data-key=name]').fill('QA Lamp');rows.nth(1).locator('[data-key=quantity]').fill('5');rows.nth(1).locator('[data-key=price]').fill('20');submit(page)
                page.locator('tbody tr').first.get_by_role('button',name='查看报价').click()
                page.get_by_role('button',name='复制为新版本').click();page.locator('dialog [data-key=price]').first.wait_for();page.locator('dialog [data-key=price]').first.fill('13.34');submit(page)
                page.locator('tbody tr').first.get_by_role('button',name='查看报价').click();page.screenshot(path=str(ROOT/'screenshots'/'03-quotation.png'),full_page=True)
                page.get_by_role('button',name='确认并转订单').click();submit(page)
                page.locator('tbody tr').first.get_by_role('button',name='查看订单').click();page.screenshot(path=str(ROOT/'screenshots'/'04-order.png'),full_page=True)
                page.get_by_role('button',name='登记收款',exact=True).click();page.locator('dialog [name=amount]').fill('100');submit(page)
                page.locator('tbody tr').first.get_by_role('button',name='查看订单').click();page.get_by_role('button',name='登记出货',exact=True).click();page.locator('dialog [name=tracking]').fill('QA-BL-01');page.locator('dialog [name=destination]').fill('Hamburg');page.locator('.shipQty').first.fill('4');submit(page)
                page.locator('tbody tr').first.get_by_role('button',name='查看订单').click();page.get_by_role('button',name='分配供货').first.click();submit(page)
                page.locator('tbody tr').first.get_by_role('button',name='查看订单').click();page.get_by_role('button',name='更新',exact=True).first.click();page.locator('dialog [name=progress]').fill('80');page.locator('dialog [name=quality]').fill('抽检合格');submit(page)
                data=page.evaluate('state.orders[0]');assert data['paid']==10000 and data['shipped']==4 and data['amount']==23340,data
                assert data['lines'][0]['tasks'][0]['progress']==80
                for name in ['工作台','客户','商机','产品','报价','订单','收款与出货','报表','设置']:
                    page.locator('#nav').get_by_role('button',name=name,exact=True).click();page.wait_for_timeout(200);assert page.locator('h1').count()==1,name
                    if name=='商机':page.screenshot(path=str(ROOT/'screenshots'/'05-opportunities.png'),full_page=True)
                page.locator('#nav').get_by_role('button',name='产品',exact=True).click()
                page.get_by_role('button',name='查看资料').first.click()
                from PIL import Image
                from io import BytesIO
                photo=BytesIO();Image.new('RGB',(120,90),'#dedaf8').save(photo,format='PNG')
                page.locator('dialog input[type=file]').set_input_files({'name':'test-product.png','mimeType':'image/png','buffer':photo.getvalue()})
                page.wait_for_function("document.querySelector('.product-art img')?.naturalWidth > 0")
                page.get_by_role('button',name='关闭',exact=True).click()
                page.screenshot(path=str(ROOT/'screenshots'/'07-products.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});page.locator('#nav .nav').first.click();page.screenshot(path=str(ROOT/'screenshots'/'06-mobile.png'),full_page=True)
                assert not errors,errors
                browser.close();print('UI PASS: login, customer, contacts, followup, quote/version, conversion, payment, partial shipment, supply progress, navigation, product image preview and mobile viewport; no browser script errors.')
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3);app.extensions['engine'].dispose()
def submit(page):
    page.locator('dialog button[type=submit]').click();page.wait_for_function("!document.querySelector('dialog').open",timeout=10000)
if __name__=='__main__':check()
