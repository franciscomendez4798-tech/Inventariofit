"""run_migration.py — Migra datos de SQLite exportados a Supabase PostgreSQL."""
import os, sys, json

def run():
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL no definida")
        sys.exit(1)

    data_path = os.path.join(os.path.dirname(__file__), "sqlite_data.json")
    with open(data_path, "r") as f:
        data = json.load(f)

    print("=== Migración SQLite → Supabase ===")

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    insert_order = [
        'Categorias', 'Departamentos', 'Proveedores', 'Dispositivos_AV',
        'Trabajadores', 'Usuarios',
        'Firmas_Trabajadores', 'Firmas_Usuarios',
        'Materiales', 'Permisos_Visibilidad',
        'Prestamos_AV', 'Ordenes_Servicio', 'Reservas_Auditorio',
        'Stock_Mantenimiento', 'Movimientos_Stock_Mant'
    ]

    extra_tables = [
        'Cotizaciones', 'Movimientos_Inventario', 'Detalle_Pedido',
        'Pedidos', 'Prestamos_Herramientas', 'Pedidos_Equipo', 'Herramientas'
    ]

    bool_cols = {'activo', 'publicado', 'disponible', 'servicio_realizado',
                 'condicion_ok', 'encuesta_completada', 'pago_verificado'}

    # 1. DELETE
    print("  Limpiando tablas...")
    for t in extra_tables:
        try:
            cur.execute(f'DELETE FROM "{t}"')
        except:
            pass
    for t in reversed(insert_order):
        try:
            cur.execute(f'DELETE FROM "{t}"')
        except:
            pass

    # 2. INSERT
    total = 0
    for table in insert_order:
        if table not in data or not data[table]['rows']:
            continue
        cols = data[table]['columns']
        rows = data[table]['rows']
        cols_sql = ', '.join(f'"{c}"' for c in cols)
        placeholders = ', '.join(['%s'] * len(cols))
        sql = f'INSERT INTO "{table}" ({cols_sql}) VALUES ({placeholders})'

        ok = 0
        for row in rows:
            vals = [bool(row[c]) if c in bool_cols and row[c] is not None else row[c] for c in cols]
            try:
                cur.execute(sql, vals)
                ok += 1
            except Exception as e:
                print(f"    WARN {table}: {str(e).splitlines()[0][:100]}")
        total += ok
        print(f"  {table}: {ok}/{len(rows)}")

    # 3. Reset sequences
    for table in insert_order:
        if table == 'Permisos_Visibilidad':
            continue
        if table in data and data[table]['rows']:
            ids = [r.get('id', 0) for r in data[table]['rows'] if r.get('id')]
            if ids:
                try:
                    cur.execute(
                        f"""SELECT setval(pg_get_serial_sequence('"{table}"', 'id'), %s, true)""",
                        (max(ids),)
                    )
                except:
                    pass

    # 4. Verify
    print("\n  Verificación:")
    for t in insert_order:
        if t in data and data[t]['rows']:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            count = cur.fetchone()[0]
            expected = len(data[t]['rows'])
            s = "✓" if count >= expected else "✗"
            print(f"    {s} {t}: {count}/{expected}")

    cur.close()
    conn.close()
    print(f"\n  Total: {total} filas insertadas")
    print("=== Migración completada ===")

if __name__ == "__main__":
    run()
