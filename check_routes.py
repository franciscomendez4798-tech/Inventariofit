"""Test directo de todas las rutas de mantenimiento con session override."""
import sys, os
os.environ['FLASK_ENV'] = 'development'

from app import create_app
from app.models import db, Usuario
from flask_login import login_user

app = create_app()
app.config['TESTING'] = True
app.config['LOGIN_DISABLED'] = True  # Desabilita @login_required

with app.app_context():
    admin = Usuario.query.filter_by(rol='administrador', activo=True).first()
    mant  = Usuario.query.filter_by(rol='mantenimiento', activo=True).first()

    test_pairs = []
    if admin:
        test_pairs.append(('ADMIN', admin))
    if mant:
        test_pairs.append(('MANTENIMIENTO', mant))

    errors = []
    ok_count = 0

    for role_name, user in test_pairs:
        print(f"\n{'='*60}")
        print(f"PROBANDO: {role_name} ({user.email})")
        print(f"{'='*60}")
        
        with app.test_client() as client:
            # Force user into session
            @app.login_manager.request_loader
            def load_user_from_request(request):
                return user

            rules = sorted(app.url_map.iter_rules(), key=lambda r: r.rule)
            for rule in rules:
                if 'GET' not in rule.methods:
                    continue
                if '<' in rule.rule or rule.endpoint == 'static':
                    continue
                if 'debugger' in rule.rule:
                    continue
                # Solo probar rutas relevantes al rol
                if role_name == 'ADMIN' and not (rule.rule.startswith('/admin') or rule.rule.startswith('/api')):
                    continue
                if role_name == 'MANTENIMIENTO' and not rule.rule.startswith('/mantenimiento'):
                    continue

                url = rule.rule
                try:
                    res = client.get(url, follow_redirects=False)
                    code = res.status_code
                    
                    if code >= 500:
                        body = res.get_data(as_text=True)
                        err_detail = ''
                        lines = body.split('\n')
                        for line in reversed(lines):
                            line = line.strip()
                            if line and ('Error' in line or 'Exception' in line):
                                err_detail = line[:200]
                                break
                        print(f"  ❌ {url} -> {code}")
                        print(f"     └─ {err_detail}")
                        errors.append({'role': role_name, 'url': url, 'code': code, 'detail': err_detail})
                    elif code in (301, 302, 308):
                        loc = res.headers.get('Location', '')
                        print(f"  ↩️  {url} -> {code} -> {loc}")
                        ok_count += 1
                    elif code == 403:
                        print(f"  🔒 {url} -> {code} (sin permiso, esperado)")
                        ok_count += 1
                    else:
                        print(f"  ✅ {url} -> {code}")
                        ok_count += 1
                except Exception as e:
                    err_str = f"{type(e).__name__}: {str(e)[:200]}"
                    print(f"  ❌ {url} -> EXCEPTION")
                    print(f"     └─ {err_str}")
                    errors.append({'role': role_name, 'url': url, 'code': 'EXC', 'detail': err_str})

    # Resumen
    print(f"\n{'='*60}")
    print("RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"  ✅ Rutas OK:        {ok_count}")
    print(f"  ❌ Errores (500+):  {len(errors)}")
    
    if errors:
        print(f"\n{'─'*60}")
        print("LISTA DE ERRORES A CORREGIR:")
        print(f"{'─'*60}")
        seen = set()
        for i, e in enumerate(errors, 1):
            key = f"{e['url']}|{e['detail'][:60]}"
            if key in seen:
                continue
            seen.add(key)
            print(f"\n  {i}. [{e['role']}] {e['url']}")
            print(f"     Status: {e['code']}")
            print(f"     Error:  {e['detail']}")
        sys.exit(1)
    else:
        print("\n🎉 ¡Todas las rutas pasaron sin errores!")
        sys.exit(0)
