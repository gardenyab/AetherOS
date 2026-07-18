import os
import subprocess
import sys
import inspect
import ast
import importlib
import urllib.request
import config as cfg

MODULES = []

def load_apps():
    global MODULES
    new_modules = []
    
    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    
    if not os.path.exists(apps_dir):
        os.makedirs(apps_dir)
        return

    if os.path.dirname(__file__) not in sys.path:
        sys.path.insert(0, os.path.dirname(__file__))

    for filename in os.listdir(apps_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"apps.{filename[:-3]}"
            try:
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                module = importlib.import_module(module_name)
                
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if obj.__module__ == module_name:
                        instance = obj()
                        new_modules = [m for m in new_modules if m.__class__.__name__ != name]
                        new_modules.append(instance)
            except Exception as e:
                print(f"[-] Error loading app {filename}: {e}")

    updated_modules = []
    new_class_names = {m.__class__.__name__ for m in new_modules}
    
    for old_mod in MODULES:
        if old_mod.__class__.__name__ not in new_class_names:
            updated_modules.append(old_mod)
            
    updated_modules.extend(new_modules)
    MODULES = updated_modules

def download_app(url):
    if not url:
        print("Error: Specify a .py file URL. Usage: install <url>")
        return

    filename = url.split('/')[-1]
    if not filename.endswith('.py'):
        print("Error: URL must point to a .py file")
        return

    apps_dir = "/root/apps"
    os.makedirs(apps_dir, exist_ok=True)
    target_path = os.path.join(apps_dir, filename)
    temp_path = os.path.join(apps_dir, f"temp_{filename}")

    print(f"[!] Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, temp_path)
        
        new_class_names = set()
        reqs_pip = []
        reqs_apt = []
        
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                node = ast.parse(f.read(), filename=temp_path)

            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    new_class_names.add(child.name)
                    for sub_child in child.body:
                        if isinstance(sub_child, ast.Assign):
                            for target in sub_child.targets:
                                if isinstance(target, ast.Name):
                                    if target.id == 'requirements' and isinstance(sub_child.value, ast.List):
                                        reqs_pip = [el.value for el in sub_child.value.elts if isinstance(el, ast.Constant)]
                                    elif target.id == 'requirementsApt' and isinstance(sub_child.value, ast.List):
                                        reqs_apt = [el.value for el in sub_child.value.elts if isinstance(el, ast.Constant)]
        except Exception as parse_err:
            print(f"[-] Warning during file analysis: {parse_err}")

        if not new_class_names:
            print("[-] Error: No class declarations found!")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return

        for existing_file in os.listdir(apps_dir):
            if existing_file.endswith('.py') and existing_file != '__init__.py' and existing_file != f"temp_{filename}":
                ex_path = os.path.join(apps_dir, existing_file)
                try:
                    with open(ex_path, "r", encoding="utf-8") as f:
                        ex_node = ast.parse(f.read(), filename=ex_path)
                    for child in ast.iter_child_nodes(ex_node):
                        if isinstance(child, ast.ClassDef) and child.name in new_class_names:
                            print(f"[!] Conflict: Class '{child.name}' exists in {existing_file}.")
                            os.remove(ex_path)
                            break
                except Exception:
                    pass

        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(temp_path, target_path)
        print(f"[+] File saved to {target_path}")

        if reqs_apt:
            print(f"[!] System apt dependencies: {', '.join(reqs_apt)}")
            try:
                subprocess.check_call(["apt-get", "update", "-qq"])
                subprocess.check_call(["apt-get", "install", "-y", *reqs_apt])
                print("[+] APT dependencies installed.")
            except Exception as apt_err:
                print(f"[-] APT error: {apt_err}")

        if reqs_pip:
            print(f"[!] Python pip dependencies: {', '.join(reqs_pip)}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", *reqs_pip])
                print("[+] PIP dependencies installed.")
            except Exception as pip_err:
                print(f"[-] PIP error: {pip_err}")

        load_apps()
        print("[+] Command list updated!")

    except Exception as e:
        print(f"[-] Failed to process file: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

def delete_app(app_name):
    if not app_name:
        print("Error: Specify module name. Usage: uninstall <name>")
        return

    filename = f"{app_name}.py" if not app_name.endswith('.py') else app_name
    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    target_path = os.path.join(apps_dir, filename)

    if not os.path.exists(target_path):
        print(f"Error: {filename} not found.")
        return

    try:
        os.remove(target_path)
        print(f"[+] App {filename} removed.")
        module_name = f"apps.{filename[:-3]}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        load_apps()
        print("[+] Command list updated!")
    except Exception as e:
        print(f"[-] Failed to remove file: {e}")
