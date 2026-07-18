import os
import subprocess
import shutil
import sys
import inspect
import importlib
import urllib.request
import readline

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

def download_app(url):
    """Скачивает .py файл по ссылке, проверяет pip-зависимости и сохраняет в ./apps/"""
    if not url:
        print("Ошибка: Укажите ссылку на .py файл. Пример: install https://site.com/test.py")
        return

    filename = url.split('/')[-1]
    if not filename.endswith('.py'):
        print("Ошибка: Ссылка должна вести на файл с расширением .py")
        return

    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    # На всякий случай проверяем, существует ли папка apps
    os.makedirs(apps_dir, exist_ok=True)
    target_path = os.path.join(apps_dir, filename)

    print(f"[!] Скачивание {filename}...")
    try:
        urllib.request.urlretrieve(url, target_path)
        print(f"[+] Файл успешно сохранен в {target_path}")
        
        # --- БЛОК АВТОУСТАНОВКИ ЗАВИСИМОСТЕЙ ---
        try:
            # Динамически загружаем скачанный модуль для проверки переменных
            module_name = filename[:-3]  # отрезаем '.py'
            spec = importlib.util.spec_from_file_location(module_name, target_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            # Проверяем, есть ли внутри файла переменная requirements
            # Поддерживаем как глобальную переменную requirements, так и self.requirements внутри класса,
            # если ты создаешь экземпляр. Здесь проверяем глобальную в модуле:
            if hasattr(mod, 'requirements'):
                reqs = mod.requirements
                if isinstance(reqs, list) and reqs:
                    print(f"[!] Обнаружены pip-зависимости: {', '.join(reqs)}")
                    print("[!] Установка зависимостей через pip...")
                    
                    # Запускаем pip install для всех зависимостей из списка
                    subprocess.check_call([sys.executable, "-m", "pip", "install", *reqs])
                    print("[+] Все зависимости успешно установлены!")
                elif reqs:
                    print("[-] Предупреждение: Переменная 'requirements' должна быть списком (list).")
        except Exception as pip_err:
            print(f"[-] Ошибка при анализе или установке зависимостей: {pip_err}")
            print("[!] Файл сохранен, но приложение может работать некорректно без ручной установки пакетов.")
        # ----------------------------------------

        load_apps()
        print("[+] Список команд успешно обновлен!")
    except Exception as e:
        print(f"[-] Не удалось скачать файл: {e}")

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

def do_install(disk="/dev/sda"):
    print("=== НАЧАЛО УСТАНОВКИ (LEGACY/MBR) ===", "\033[93m")
    part = f"{disk}1"

    if not os.path.exists(disk):
        print(f"[-] Ошибка: Диск {disk} не найден!", "\033[91m")
        return False

    print("1. Разметка диска (MBR)...", "\033[96m")
    if not run_cmd(["parted", "-s", disk, "mklabel", "msdos"]): return False
    if not run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "1MiB", "100%"]): return False
    if not run_cmd(["parted", "-s", disk, "set", "1", "boot", "on"]): return False

    print("2. Форматирование в ext4...", "\033[96m")
    if not run_cmd(["mkfs.ext4", "-F", part]):
        print("[-] Ошибка форматирования!", "\033[91m")
        return False

    print("3. Монтирование...", "\033[96m")
    os.makedirs("/mnt", exist_ok=True)
    run_cmd(["umount", "-q", "/mnt"]) # На всякий случай отмонтируем, если что-то зависло
    if not run_cmd(["mount", part, "/mnt"]): return False

    print("4. Копирование файлов (rsync)...", "\033[96m")
    rsync_cmd = [
        "rsync", "-aHAXx", 
        "--exclude=/proc/*", "--exclude=/sys/*", 
        "--exclude=/dev/*", "--exclude=/mnt/*", 
        "--exclude=/tmp/*", "--exclude=/run/*", 
        "/", "/mnt/"
    ]
    if not run_cmd(rsync_cmd): return False

    print("5. Подготовка fstab...", "\033[96m")
    # Пытаемся получить UUID для надежной загрузки, если не выйдет — используем part
    try:
        uuid = subprocess.check_output(["blkid", "-s", "UUID", "-o", "value", part]).decode().strip()
        mount_point = f"UUID={uuid}"
    except Exception:
        mount_point = part

    with open("/mnt/etc/fstab", "w") as fst:
        fst.write(f"{mount_point}  /  ext4  errors=remount-ro  0  1\n")

    print("6. Установка GRUB (через chroot)...", "\033[96m")
    
    # Для правильной работы grub-install внутри chroot ему нужны системные директории
    run_cmd(["mount", "--bind", "/dev", "/mnt/dev"])
    run_cmd(["mount", "--bind", "/proc", "/mnt/proc"])
    run_cmd(["mount", "--bind", "/sys", "/mnt/sys"])
    run_cmd(["mount", "--bind", "/run", "/mnt/run"])

    # Запускаем grub-install прямо "изнутри" будущей системы
    chroot_grub = f"chroot /mnt grub-install {disk}"
    if not run_cmd(["bash", "-c", chroot_grub]):
        print("[-] Ошибка установки загрузчика GRUB в MBR!", "\033[91m")
        # Не забываем отмонтировать шины перед выходом при ошибке
        for p in ["/run", "/sys", "/proc", "/dev"]: run_cmd(["umount", f"/mnt{p}"])
        return False
        
    # Отмонтируем системные шины обратно
    for p in ["/run", "/sys", "/proc", "/dev"]: 
        run_cmd(["umount", "-l", f"/mnt{p}"])
    
    print("7. Генерация grub.cfg...", "\033[96m")
    os.makedirs("/mnt/boot/grub", exist_ok=True)
    
    import glob
    
    # Динамический поиск файлов ядра и initrd
    vmlinuz_files = glob.glob("/mnt/boot/vmlinuz-*")
    initrd_files = glob.glob("/mnt/boot/initrd.img-*")
    
    # Если файлы найдены, отрезаем префикс /mnt, чтобы путь был правильным для GRUB
    kernel_path = vmlinuz_files[0].replace("/mnt", "") if vmlinuz_files else "/boot/vmlinuz"
    initrd_path = initrd_files[0].replace("/mnt", "") if initrd_files else "/boot/initrd.img"

    with open("/mnt/boot/grub/grub.cfg", "w") as f:
        f.write("set timeout=3\n")
        f.write("set default=0\n")
        f.write("menuentry 'AetherOS (Installed)' {\n")
        f.write("    insmod part_msdos\n")
        f.write("    insmod ext2\n")
        f.write("    set root='(hd0,msdos1)'\n")
        f.write(f"    linux {kernel_path} root={mount_point} ro quiet\n")
        f.write(f"    initrd {initrd_path}\n")
        f.write("}\n")

    print("8. Очистка и размонтирование...", "\033[96m")
    run_cmd(["umount", "/mnt"])

    print("=== УСТАНОВКА ЗАВЕРШЕНА! МОЖНО ПЕРЕЗАГРУЖАТЬСЯ ===", "\033[92m")
    return True

def show_help():
    """Автоматический генератор справки по системе и модулям"""
    load_apps()
    
    print("\n      AETHER OS v1 — СПРАВКА ПО КОМАНДАМ")
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
    print("~ Commands: help, clear, install, install-system, update, uninstall, shutdown")
    
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
            elif cmd == 'install-system':
                install_system_to_disk()
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