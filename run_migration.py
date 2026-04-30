"""run_migration.py — Ejecuta migration_supabase.sql en la DB de producción."""
import os, sys

def run():
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL no definida")
        sys.exit(1)

    print("=== Ejecutando migración SQLite → Supabase ===")

    with open("migration_supabase.sql", "r") as f:
        sql = f.read()

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    ok = 0
    errors = 0
    for i, stmt in enumerate(statements):
        try:
            cur.execute(stmt)
            ok += 1
        except Exception as e:
            errors += 1
            print(f"  WARN [{i+1}]: {str(e).strip().splitlines()[0][:100]}")

    # Verify counts
    tables = [
        "Usuarios", "Departamentos", "Categorias", "Proveedores",
        "Trabajadores", "Materiales", "Ordenes_Servicio",
        "Permisos_Visibilidad", "Dispositivos_AV"
    ]
    print(f"\n  Ejecutados: {ok} OK, {errors} errores")
    print("  Verificación:")
    for t in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            count = cur.fetchone()[0]
            if count > 0:
                print(f"    {t}: {count} filas")
        except:
            pass

    cur.close()
    conn.close()
    print("=== Migración completada ===")

if __name__ == "__main__":
    run()
