"""run_migration.py — Migra datos de SQLite exportados a Supabase PostgreSQL."""
import os, sys, json

def run():
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL no definida")
        sys.exit(1)

    # Load exported data
    data_path = os.path.join(os.path.dirname(__file__), "sqlite_data.json")
    with open(data_path, "r") as f:
        data = json.load(f)

    print("=== Migración SQLite → Supabase (parametrizada) ===")

    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()

    # Order: children first for DELETE, parents first for INSERT
    insert_order = [
        'Categorias', 'Departamentos', 'Proveedores', 'Dispositivos_AV',
        'Trabajadores', 'Usuarios',
        'Firmas_Trabajadores', 'Firmas_Usuarios',
        'Materiales', 'Permisos_Visibilidad',
        'Prestamos_AV', 'Ordenes_Servicio', 'Reservas_Auditorio',
        'Stock_Mantenimiento', 'Movimientos_Stock_Mant'
    ]

    # Also clean tables that might have orphaned data
    extra_tables = [
        'Cotizaciones', 'Movimientos_Inventario', 'Detalle_Pedido',
        'Pedidos', 'Prestamos_Herramientas', 'Pedidos_Equipo', 'Herramientas'
    ]

    try:
        # 1. DELETE all in reverse FK order
        print("  Limpiando tablas...")
        for t in extra_tables:
            cur.execute(f'DELETE FROM "{t}"')
        for t in reversed(insert_order):
            cur.execute(f'DELETE FROM "{t}"')

        # 2. INSERT data using parameterized queries
        total_inserted = 0
        for table in insert_order:
            if table not in data:
                continue
            tdata = data[table]
            cols = tdata['columns']
            rows = tdata['rows']
            if not rows:
                continue

            cols_sql = ', '.join(f'"{c}"' for c in cols)
            placeholders = ', '.join(['%s'] * len(cols))
            insert_sql = f'INSERT INTO "{table}" ({cols_sql}) VALUES ({placeholders})'

            ok = 0
            for row in rows:
                values = []
                for c in cols:
                    v = row[c]
                    # Convert SQLite boolean (0/1) to Python bool for boolean columns
                    if c in ('activo', 'publicado', 'disponible', 'servicio_realizado',
                             'condicion_ok', 'encuesta_completada', 'pago_verificado'):
                        if v is not None:
                            v = bool(v)
                    values.append(v)
                try:
                    cur.execute(insert_sql, values)
                    ok += 1
                except Exception as e:
                    msg = str(e).strip().splitlines()[0][:120]
                    print(f"    WARN {table}: {msg}")
                    conn.rollback()
                    # Re-delete and re-insert everything for this table
                    # Skip this individual row and continue
                    conn.autocommit = True
                    cur.execute(insert_sql, values)  # retry with autocommit
                    conn.autocommit = False
                    ok += 1

            total_inserted += ok
            print(f"  {table}: {ok}/{len(rows)} filas")

        # 3. Reset sequences
        print("  Reseteando secuencias...")
        conn.autocommit = True
        for table in insert_order:
            if table == 'Permisos_Visibilidad':
                continue
            if table in data and data[table]['rows']:
                ids = [r.get('id', 0) for r in data[table]['rows'] if r.get('id')]
                if ids:
                    max_id = max(ids)
                    try:
                        cur.execute(
                            f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), %s, true)",
                            (max_id,)
                        )
                    except Exception as e:
                        print(f"    Seq {table}: {str(e).splitlines()[0][:80]}")

        # 4. Verify
        print("\n  Verificación:")
        for t in insert_order:
            if t in data and data[t]['rows']:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                count = cur.fetchone()[0]
                expected = len(data[t]['rows'])
                status = "✓" if count >= expected else "✗"
                print(f"    {status} {t}: {count}/{expected}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR FATAL: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print(f"\n  Total insertadas: {total_inserted} filas")
    print("=== Migración completada ===")

if __name__ == "__main__":
    run()
