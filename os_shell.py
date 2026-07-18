import os
import subprocess
import shutil
import sys
import inspect
import ast
import importlib
import importlib.util
import urllib.request
import readline

MODULES = []

def load_apps():
    """Динамически загружает все модули из папки ./apps/ с жесткой перезаписью дубликатов классов"""
    global MODULES
    # Не очищаем весь список MODULES полностью, если хотим выборочно перезаписывать дубликаты,
    # либо очищаем, но фильтруем на лету. Безопаснее собирать новый список и фильтровать старые.
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
                # ХАК ДЛЯ ПЕРЕЗАПИСИ: Удаляем модуль из кэша Python, чтобы он 100% прочитал файл с диска
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                # Импортируем модуль начисто
                module = importlib.import_module(module_name)
                
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if obj.__module__ == module_name:
                        instance = obj()
                        
                        # Проверяем, нет ли уже загруженного класса с таким именем в новом списке
                        # (на случай, если в разных файлах папки apps лежат классы с одинаковым именем)
                        new_modules = [m for m in new_modules if m.__class__.__name__ != name]
                        
                        new_modules.append(instance)
                        
            except Exception as e:
                print(f"[-] Ошибка загрузки приложения {filename}: {e}")

    # Теперь жестко обновляем глобальный список модулей, вычищая старые дубликаты
    # Если в MODULES были встроенные команды (не из папки apps), мы их сохраняем, 
    # заменяя только те, чьи имена совпали с новыми классами из папки apps.
    updated_modules = []
    new_class_names = {m.__class__.__name__ for m in new_modules}
    
    # Оставляем старые системные команды, которых нет среди новых аппов
    for old_mod in MODULES:
        if old_mod.__class__.__name__ not in new_class_names:
            updated_modules.append(old_mod)
            
    # Добавляем все свежезагруженные аппы
    updated_modules.extend(new_modules)
    
    MODULES = updated_modules

def download_app(url):
    """Скачивает .py файл по ссылке, удаляет старые файлы с конфликтующими классами,

    ставит зависимости apt/pip и регистрирует приложение.
    """
    if not url:
        print("Ошибка: Укажите ссылку на .py файл. Пример: install https://site.com/test.py")
        return

    filename = url.split('/')[-1]
    if not filename.endswith('.py'):
        print("Ошибка: Ссылка должна вести на файл с расширением .py")
        return

    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    os.makedirs(apps_dir, exist_ok=True)
    target_path = os.path.join(apps_dir, filename)

    # Временный путь для безопасного анализа структуры нового файла до его окончательного сохранения
    temp_path = os.path.join(apps_dir, f"temp_{filename}")

    print(f"[!] Скачивание {filename}...")
    try:
        # Сначала скачиваем во временный файл, чтобы проанализировать структуру и имена классов
        urllib.request.urlretrieve(url, temp_path)
        
        # --- БЛОК АНАЛИЗА НОВОГО ФАЙЛА ЧЕРЕЗ AST ---
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
                                    # Ищем pip-зависимости
                                    if target.id == 'requirements' and isinstance(sub_child.value, ast.List):
                                        reqs_pip = [el.value for el in sub_child.value.elts if isinstance(el, ast.Constant)]
                                    # Ищем apt-зависимости
                                    elif target.id == 'requirementsApt' and isinstance(sub_child.value, ast.List):
                                        reqs_apt = [el.value for el in sub_child.value.elts if isinstance(el, ast.Constant)]
        except Exception as parse_err:
            print(f"[-] Предупреждение при анализе структуры нового файла: {parse_err}")

        if not new_class_names:
            print("[-] Ошибка: В скачанном файле не найдено объявлений классов!")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return

        # --- БЛОК УДАЛЕНИЯ СТАРЫХ ФАЙЛОВ-ДУБЛИКАТОВ ---
        # Проверяем существующие файлы в папке apps. Если в них есть класс с таким же именем — удаляем файл.
        for existing_file in os.listdir(apps_dir):
            if existing_file.endswith('.py') and existing_file != '__init__.py' and existing_file != f"temp_{filename}":
                ex_path = os.path.join(apps_dir, existing_file)
                try:
                    with open(ex_path, "r", encoding="utf-8") as f:
                        ex_node = ast.parse(f.read(), filename=ex_path)
                    
                    for child in ast.iter_child_nodes(ex_node):
                        if isinstance(child, ast.ClassDef) and child.name in new_class_names:
                            print(f"[!] Конфликт: Класс '{child.name}' уже существует в файле {existing_file}.")
                            print(f"[!] Удаление старого файла: {ex_path}")
                            os.remove(ex_path)
                            break # Файл удален, переходим к следующему
                except Exception:
                    pass # Если файл битый или не парсится, просто пропускаем его

        # Перемещаем временный файл на его постоянное место
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(temp_path, target_path)
        print(f"[+] Файл успешно сохранен в {target_path}")

        # --- УСТАНОВКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ (APT) ---
        if reqs_apt:
            print(f"[!] Обнаружены системные apt-зависимости: {', '.join(reqs_apt)}")
            print("[!] Установка системных пакетов через apt (может потребоваться время)...")
            try:
                # Обновляем кэш apt и ставим пакеты без лишних вопросов (-y)
                subprocess.check_call(["apt-get", "update", "-qq"])
                subprocess.check_call(["apt-get", "install", "-y", *reqs_apt])
                print("[+] Все apt-зависимости успешно установлены!")
            except Exception as apt_err:
                print(f"[-] Ошибка при установке пакетов через apt: {apt_err}")
                print("[!] Пробуем продолжить...")

        # --- УСТАНОВКА PYTHON ЗАВИСИМОСТЕЙ (PIP) ---
        if reqs_pip:
            print(f"[!] Обнаружены pip-зависимости класса: {', '.join(reqs_pip)}")
            print("[!] Установка зависимостей через pip...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", *reqs_pip])
                print("[+] Все pip-зависимости успешно установлены!")
            except Exception as pip_err:
                print(f"[-] Ошибка при установке пакетов через pip: {pip_err}")
                print("[!] Пробуем продолжить, но приложение может работать некорректно.")
        else:
            print("[*] У класса не обнаружено pip-зависимостей.")

        # --- СИСТЕМНЫЙ ИМПОРТ И РЕГИСТРАЦИЯ КОМАНД ---
        try:
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, target_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            # Обновляем глобальный список MODULES через обновленный load_apps()
            load_apps()
            print("[+] Список команд успешно обновлен!")
        except Exception as load_err:
            print(f"[-] Ошибка при загрузке модуля в систему: {load_err}")

    except Exception as e:
        print(f"[-] Не удалось обработать и установить файл: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

def delete_app(app_name):
    """Удаляет приложение из папки ./apps/"""
    if not app_name:
        print("Ошибка: Укажите имя модуля или файла для удаления. Пример: uninstall test")
        return

    if not app_name.endswith('.py'):
        filename = f"{app_name}.py"
    else:
        filename = app_name

    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    target_path = os.path.join(apps_dir, filename)

    if not os.path.exists(target_path):
        print(f"Ошибка: Файл {filename} не найден в папке ./apps/")
        return

    try:
        os.remove(target_path)
        print(f"[+] Приложение {filename} успешно удалено.")
        
        module_name = f"apps.{filename[:-3]}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        load_apps()
        print("[+] Список команд успешно обновлен!")
    except Exception as e:
        print(f"[-] Не удалось удалить файл: {e}")

def show_help():
    """Автоматический генератор справки по системе и модулям"""
    load_apps()
    
    print("\n      AETHER OS v2 — СПРАВКА ПО КОМАНДАМ")
    print("====================================================")
    print("📦 Встроенные системные команды:")
    print("  ↳ install-system   - Установить Aether OS с Live-ISO на жесткий диск")
    print("  ↳ install <url>    - Скачать и установить .py модуль по ссылке")
    print("  ↳ uninstall <name> - Удалить установленный модуль")
    print("  ↳ update           - Проверить и установить обновления из Git")
    print("  ↳ shutdown         - Выключить ПК")
    print("  ↳ help             - Показать эту справку")
    print("  ↳ clear            - Очистить экран")
    print("  ↳ exit / q         - Выйти из оболочки")
    
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
    
    # --- Инициализация Readline (Стрелочки, Навигация, Вставка) ---
    readline.set_history_length(100)
    
    # Функция автодополнения по Tab
    def completer(text, state):
        builtins = ['help', 'clear', 'install', 'uninstall', 'install-system', 'update', 'shutdown', 'exit', 'q']
        app_cmds = []
        for module in MODULES:
            app_cmds.extend([name for name, _ in inspect.getmembers(module, inspect.ismethod) if not name.startswith('_')])
        
        options = [cmd for cmd in (builtins + app_cmds) if cmd.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    # -------------------------------------------------------------
    
    free_space = shutil.disk_usage('/').free // (1024**2)
    
    print("AetherOS v1")
    print("~ Commands: help, clear, install, update, uninstall, shutdown")
    
    while True:
        try:
            user_input = input("AetherOS ~ ").strip()
            if not user_input:
                continue
                
            parts = user_input.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd == 'help':
                show_help()
                continue
            elif cmd == 'clear':
                os.system('clear')
                continue
            elif cmd == 'install':
                url_arg = args[0] if args else None
                download_app(url_arg)
                continue
            elif cmd == 'uninstall':
                app_arg = args[0] if args else None
                delete_app(app_arg)
                continue
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