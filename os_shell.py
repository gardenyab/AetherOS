import os
import subprocess
import shutil
import sys
import inspect
import importlib

# Список динамически загруженных экземпляров классов-приложений
MODULES = []

def load_apps():
    """Динамически загружает все модули из папки ./apps/"""
    global MODULES
    MODULES.clear()
    
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
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = importlib.import_module(module_name)
                
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if obj.__module__ == module_name:
                        MODULES.append(obj())
            except Exception as e:
                print(f"[-] Ошибка загрузки приложения {filename}: {e}")

def show_help():
    """Автоматический генератор справки по системе и модулям"""
    load_apps()
    
    print("\n      AETHER OS v1 — СПРАВКА ПО КОМАНДАМ")
    print("====================================================")
    print("📦 Встроенные системные команды:")
    print(f"  ↳ install      - Запустить установщик системы")
    print(f"  ↳ update       - Проверить и установить обновления из Git")
    print(f"  ↳ shutdown     - Выключить ПК")
    print(f"  ↳ help         - Показать эту справку")
    print(f"  ↳ clear        - Очистить экран")
    print(f"  ↳ exit / q     - Выйти из оболочки")
    
    if not MODULES:
        print("\n📦 Модули в ./apps/ не обнаружены.")
    else:
        for module in MODULES:
            class_name = module.__class__.__name__.lower()
            class_doc = module.__class__.__doc__ or "Нет описания"
            
            print(f"\n📦 Модуль: {class_name} ({class_doc})")
            
            methods = inspect.getmembers(module, predicate=inspect.ismethod)
            for name, method in methods:
                if not name.startswith('_'):
                    doc = method.__doc__ or "Описание отсутствует"
                    first_line_doc = doc.strip().split('\n')[0]
                    print(f"  ↳ {name:<12} - {first_line_doc}")
                    
    print("====================================================\n")

def update_system():
    project_path = "/root"
    print(f"\n[!] Checking for updates...")
    if not os.path.exists(os.path.join(project_path, ".git")):
        print("[-] Error: Not a git repository!")
        return
    try:
        subprocess.run(["git", "-C", project_path, "fetch", "origin"], check=True, capture_output=True)
        local = subprocess.check_output(["git", "-C", project_path, "rev-parse", "HEAD"]).decode().strip()
        remote = subprocess.check_output(["git", "-C", project_path, "rev-parse", "origin/main"]).decode().strip()
        if local == remote:
            print("[+] System is already up to date.")
            return
        print("[!] Updates found. Applying...")
        subprocess.run(["git", "-C", project_path, "reset", "--hard", "origin/main"], check=True)
        print("[+] System updated successfully!\n[!] Restarting shell...")
        os.execv(sys.executable, ['python3'] + sys.argv)
    except Exception as e:
        print(f"[-] Update failed: {e}")

def start_shell():
    """Единая интерактивная оболочка Aether OS"""
    os.system('clear')
    load_apps()
    
    # Считаем место для красивого приветствия
    free_space = shutil.disk_usage('/').free // (1024**2)
    
    print("----------------------------------------------------")
    print(f"       Добро пожаловать в AETHER OS v1")
    print(f"       Свободно на диске: {free_space} MB")
    print("       Введите 'help' для вывода списка команд.")
    print("----------------------------------------------------")
    
    while True:
        try:
            user_input = input("AetherOS # ").strip()
            if not user_input:
                continue
                
            parts = user_input.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            # 1. Обработка встроенных системных команд
            if cmd == 'help':
                show_help()
                continue
            elif cmd == 'clear':
                os.system('clear')
                continue
            elif cmd == 'install':
                print("\nStarting installer...")
                subprocess.run(["python3", "/root/installer.py"])
                input("\nInstaller finished. Press Enter to continue...")
                continue
            elif cmd == 'update':
                update_system()
                input("\nPress Enter to continue...")
                continue
            elif cmd == 'shutdown':
                print("\nShutting down...")
                subprocess.run(["poweroff"])
                continue
            elif cmd in ['exit', 'q']:
                print("Exiting Aether OS...")
                break
                
            # 2. Поиск команды в динамических модулях из ./apps/
            command_found = False
            for module in MODULES:
                if hasattr(module, cmd):
                    method = getattr(module, cmd)
                    if inspect.ismethod(method) and not cmd.startswith('_'):
                        method(args)
                        command_found = True
                        break
            
            if not command_found:
                print(f"Ошибка: команда '{cmd}' не найдена. Введите 'help' для справки.")
                
        except (KeyboardInterrupt, EOFError):
            print("\nИспользуйте 'exit' или 'q' для выхода.")

if __name__ == "__main__":
    if os.isatty(sys.stdin.fileno()):
        start_shell()
    else:
        print("Error: Not a TTY")