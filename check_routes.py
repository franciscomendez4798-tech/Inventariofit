import sys
from app import create_app
from app.models import db, Usuario

app = create_app()

with app.test_client() as client:
    with app.app_context():
        admin = Usuario.query.filter_by(es_admin=True).first()
        if not admin:
            print("No admin user found.")
            sys.exit(1)
            
        print(f"Testing routes as {admin.email} (Admin)")
        
        # Manually log in using Flask-Login
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        rules = app.url_map.iter_rules()
        errors = []
        for rule in rules:
            if 'GET' in rule.methods and '<' not in rule.rule:
                url = rule.rule
                try:
                    res = client.get(url)
                    if res.status_code >= 500:
                        print(f"❌ {url} -> {res.status_code}")
                        errors.append(url)
                    else:
                        print(f"✅ {url} -> {res.status_code}")
                except Exception as e:
                    print(f"❌ {url} -> Exception: {e}")
                    errors.append(url)
                    
        if errors:
            print("\n--- ERRORES ENCONTRADOS ---")
            for url in errors:
                print(url)
            sys.exit(1)
        else:
            print("\n✅ Todas las rutas pasaron sin errores de código 500.")
