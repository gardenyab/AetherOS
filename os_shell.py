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
    """Скачивает .py файл по ссылке и сохраняет в ./apps/"""
    if not url:
        print("Ошибка: Укажите ссылку на .py файл. Пример: install https://site.com/test.py")
        return

    filename = url.split('/')[-1]
    if not filename.endswith('.py'):
        print("Ошибка: Ссылка должна вести на файл с расширением .py")
        return

    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    target_path = os.path.join(apps_dir, filename)

    print(f"[!] Скачивание {filename}...")
    try:
        urllib.request.urlretrieve(url, target_path)
        print(f"[+] Файл успешно сохранен в {target_path}")
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

def install_system_to_disk():
    """Инсталлятор Aether OS на жесткий диск/SSD с автоматической установкой зависимостей и UEFI"""
    print("\n====================================================")
    print("       AETHER OS — МАСТЕР УСТАНОВКИ НА ДИСК")
    print("====================================================")
    
    if os.getuid() != 0:
        print("[-] Ошибка: Для установки системы требуются права root (sudo)!")
        return

    # Настройка правильного PATH для поиска админских утилит (mkfs, parted)
    env = os.environ.copy()
    additional_paths = ["/sbin", "/usr/sbin", "/usr/local/sbin"]
    current_path = env.get("PATH", "")
    for path in additional_paths:
        if path not in current_path:
            current_path = f"{path}:{current_path}" if current_path else path
    env["PATH"] = current_path

    # Автоматическая проверка и доустановка утилит в самом Live-ISO хосте
    print("[!] Проверка базовых зависимостей в Live-системе...")
    required_tools = ["parted", "mkfs.vfat", "mkfs.ext4", "rsync", "grub-install"]
    missing_tools = [tool for tool in required_tools if not shutil.which(tool, path=current_path)]
    
    if missing_tools:
        print(f"[!] В Live-ISO не найдены: {', '.join(missing_tools)}. Устанавливаем зависимости...")
        try:
            subprocess.run(["apt", "update"], check=True, env=env)
            subprocess.run(["apt", "install", "-y", "parted", "e2fsprogs", "dosfstools", "rsync", "grub-efi-amd64-bin"], check=True, env=env)
            print("[+] Базовые зависимости хоста успешно установлены.")
        except Exception as e:
            print(f"[-] Не удалось установить утилиты хоста автоматически: {e}")
            return

    # 1. Вывод списка накопителей
    print("\n[!] Доступные накопители в системе:")
    try:
        subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TYPE"], check=True, env=env)
    except Exception:
        print("[-] Не удалось получить список дисков через lsblk.")
        return

    drive = input("\nВведите имя диска для установки (например, sda или nvme0n1): ").strip()
    if not drive:
        print("[-] Отменено.")
        return

    target_disk = f"/dev/{drive}"
    if not os.path.exists(target_disk):
        print(f"[-] Ошибка: Диск {target_disk} не найден!")
        return

    confirm = input(f"⚠️ ВНИМАНИЕ! Все данные на {target_disk} БУДУТ УНИЧТОЖЕНЫ! Продолжить? (y/N): ").strip().lower()
    if confirm != 'y':
        print("[-] Установка отменена.")
        return

    mount_dir = "/mnt/target_aether"
    boot_efi_dir = os.path.join(mount_dir, "boot/efi")
    vfs_mounted = []

    try:
        print(f"\n[!] Подготовка диска {target_disk} (отмонтирование активных разделов)...")
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    if target_disk in line:
                        mount_point = line.split()[1]
                        subprocess.run(["umount", "-l", mount_point], env=env, capture_output=True)
            subprocess.run(["swapoff", "-a"], env=env, capture_output=True)
        except Exception:
            pass

        print(f"\n[1/5] Очистка и разметка диска {target_disk} (GPT)...")
        subprocess.run(["parted", "-s", target_disk, "mklabel", "gpt"], check=True, env=env)
        subprocess.run(["parted", "-s", target_disk, "mkpart", "ESP", "fat32", "1MiB", "513MiB"], check=True, env=env)
        subprocess.run(["parted", "-s", target_disk, "set", "1", "esp", "on"], check=True, env=env)
        subprocess.run(["parted", "-s", target_disk, "mkpart", "root", "ext4", "513MiB", "100%"], check=True, env=env)

        # Определение разметки NVMe (p1, p2) или SATA (1, 2)
        p1 = f"{target_disk}p1" if "nvme" in target_disk else f"{target_disk}1"
        p2 = f"{target_disk}p2" if "nvme" in target_disk else f"{target_disk}2"

        print("\n[2/5] Форматирование разделов...")
        subprocess.run(["mkfs.vfat", "-F", "32", p1], check=True, env=env)
        subprocess.run(["mkfs.ext4", "-F", p2], check=True, env=env)

        print("\n[3/5] Монтирование новой файловой системы...")
        os.makedirs(mount_dir, exist_ok=True)
        subprocess.run(["mount", p2, mount_dir], check=True, env=env)
        os.makedirs(boot_efi_dir, exist_ok=True)
        subprocess.run(["mount", p1, boot_efi_dir], check=True, env=env)

        print("\n[4/5] Копирование системных файлов (это может занять время)...")
        subprocess.run([
            "rsync", "-aHAXx", "--info=progress2",
            "--exclude=/proc/*", "--exclude=/sys/*", "--exclude=/dev/*", 
            "--exclude=/run/*", "--exclude=/tmp/*", "--exclude=/mnt/*", 
            "/", mount_dir
        ], check=True, env=env)

        print("\n[5/5] Установка и настройка загрузчика GRUB...")
        # Монтируем виртуальные директории API ядра, необходимые для chroot, интернета и работы с NVRAM материнки
        for vfs in ["dev", "proc", "sys", "run"]:
            subprocess.run(["mount", "--bind", f"/{vfs}", f"{mount_dir}/{vfs}"], check=True, env=env)
            vfs_mounted.append(vfs)

        # Копируем DNS-настройки, чтобы внутри chroot работал интернет для установки пакетов
        try:
            shutil.copyfile("/etc/resolv.conf", f"{mount_dir}/etc/resolv.conf")
        except Exception:
            pass

        # Принудительно ставим пакет бинарников GRUB UEFI внутрь устанавливаемой системы
        print("[!] Доустановка EFI-компонентов GRUB в целевую систему...")
        try:
            subprocess.run(["chroot", mount_dir, "apt", "update"], check=True, env=env)
            subprocess.run(["chroot", mount_dir, "apt", "install", "-y", "grub-efi-amd64-bin", "grub-efi"], check=True, env=env)
        except Exception as e:
            print(f"[!] Предупреждение при обновлении пакетов в chroot: {e}. Пробуем продолжить...")

        # Ставим GRUB и генерируем конфиг изнутри chroot окружения нового диска
        subprocess.run(["chroot", mount_dir, "grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi", "--bootloader-id=AetherOS"], check=True, env=env)
        subprocess.run(["chroot", mount_dir, "grub-mkconfig", "-o", "/boot/grub/grub.cfg"], check=True, env=env)

        print("\n[!] Завершение работы с диском и размонтирование разделов...")
        # Размонтируем виртуальные папки
        for vfs in reversed(vfs_mounted):
            subprocess.run(["umount", f"{mount_dir}/{vfs}"], check=True, env=env)
        vfs_mounted.clear()
        
        # Размонтируем основные разделы диска
        subprocess.run(["umount", boot_efi_dir], check=True, env=env)
        subprocess.run(["umount", mount_dir], check=True, env=env)

        print("\n[+] УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!")
        print("[!] Перезагрузите компьютер, предварительно извлекая Live-носитель.")

    except Exception as e:
        print(f"\n[-] Ошибка в процессе установки системы: {e}")
        print("[!] Пытаемся безопасно размонтировать оставшиеся ресурсы...")
        
        # Экстренное размонтирование в случае падения на каком-то из шагов
        for vfs in reversed(vfs_mounted):
            try: subprocess.run(["umount", f"{mount_dir}/{vfs}"], env=env, capture_output=True)
            except Exception: pass
        try: subprocess.run(["umount", boot_efi_dir], env=env, capture_output=True)
        except Exception: pass
        try: subprocess.run(["umount", mount_dir], env=env, capture_output=True)
        except Exception: pass
        print("[!] Очистка завершена. Проверьте логи.")
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