import subprocess
import os
import shutil
import sys
import time

def log(text, color=""):
    # Цвета для терминала (опционально)
    print(f"{color}{text}\033[0m")

def run_cmd(cmd):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(res.stderr)
        log(f"ОШИБКА: {' '.join(cmd)}\n{res.stderr}", "\033[91m")
        return False
    return True

def do_install():
    log("=== НАЧАЛО УСТАНОВКИ ===", "\033[93m")
    disk = "/dev/sda"
    part = "/dev/sda1"

    if not os.path.exists(disk):
        log(f"Ошибка: Диск {disk} не найден!", "\033[91m")
        return False

    log("1. Разметка диска...", "\033[96m")
    if not run_cmd(["parted", "-s", disk, "mklabel", "msdos"]): return False
    if not run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "1MiB", "100%"]): return False
    if not run_cmd(["parted", "-s", disk, "set", "1", "boot", "on"]): return False

    log("2. Форматирование...", "\033[96m")
    if not run_cmd(["mkfs.ext4", "-F", "-F", part]):pass

    log("3. Монтирование...", "\033[96m")
    os.makedirs("/mnt", exist_ok=True)
    if not run_cmd(["mount", part, "/mnt"]): return False

    log("4. Копирование файлов (rsync)...", "\033[96m")
    rsync_cmd = ["rsync", "-aHAXx", "--exclude=/proc/*", "--exclude=/sys/*", 
                 "--exclude=/dev/*", "--exclude=/mnt/*", "--exclude=/tmp/*", "/", "/mnt/"]
    if not run_cmd(rsync_cmd): return False

    log("5. Подготовка fstab...", "\033[96m")
    with open("/mnt/etc/fstab", "w") as fst:
        fst.write(f"{part}  /  ext4  errors=remount-ro  0  1\n")

    log("6. Установка GRUB...", "\033[96m")
    if not run_cmd(["grub-install", "--root-directory=/mnt", disk]): return False
    
    # Генерация конфига
    os.makedirs("/mnt/boot/grub", exist_ok=True)
    with open("/mnt/boot/grub/grub.cfg", "w") as f:
        f.write(f"menuentry 'My Python OS' {{ insmod ext2; set root=(hd0,1); linux /vmlinuz root={part} ro; initrd /initrd.img }}\n")

    log("УСТАНОВКА ЗАВЕРШЕНА!", "\033[92m")
    return True

if __name__ == "__main__":
    # Простейшее меню
    print("--- УСТАНОВЩИК OS ---")
    choice = input("Начать установку на /dev/sda? (y/n): ")
    if choice.lower() == 'y':
        if do_install():
            input("Готово! Нажмите Enter для перезагрузки...")
            subprocess.run(["reboot"])
    else:
        print("Отмена.")