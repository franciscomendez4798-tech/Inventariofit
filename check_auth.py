import ast
import sys

def check_file(filename):
    with open(filename, 'r') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            is_route = False
            has_auth = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') == 'route':
                    is_route = True
                if getattr(dec, 'id', '') in ['login_required', 'solo_admin', 'solo_solicitante', 'solo_admin_o_mantenimiento', 'solo_mantenimiento']:
                    has_auth = True
            
            if is_route and not has_auth:
                print(f"Missing Auth in {filename} -> {node.name}")

check_file('app/admin/routes.py')
check_file('app/mantenimiento/routes.py')
check_file('app/solicitante/routes.py')
check_file('app/main/routes.py') 
