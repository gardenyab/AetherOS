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

def do_install(disk="/dev/sda"):
    log("=== НАЧАЛО УСТАНОВКИ (LEGACY/MBR) ===", "\033[93m")
    part = f"{disk}1"

    if not os.path.exists(disk):
        log(f"[-] Ошибка: Диск {disk} не найден!", "\033[91m")
        return False

    log("1. Разметка диска (MBR)...", "\033[96m")
    if not run_cmd(["parted", "-s", disk, "mklabel", "msdos"]): return False
    if not run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "1MiB", "100%"]): return False
    if not run_cmd(["parted", "-s", disk, "set", "1", "boot", "on"]): return False

    log("2. Форматирование в ext4...", "\033[96m")
    if not run_cmd(["mkfs.ext4", "-F", part]):
        log("[-] Ошибка форматирования!", "\033[91m")
        return False

    log("3. Монтирование...", "\033[96m")
    os.makedirs("/mnt", exist_ok=True)
    run_cmd(["umount", "-q", "/mnt"]) # На всякий случай отмонтируем, если что-то зависло
    if not run_cmd(["mount", part, "/mnt"]): return False

    log("4. Копирование файлов (rsync)...", "\033[96m")
    rsync_cmd = [
        "rsync", "-aHAXx", 
        "--exclude=/proc/*", "--exclude=/sys/*", 
        "--exclude=/dev/*", "--exclude=/mnt/*", 
        "--exclude=/tmp/*", "--exclude=/run/*", 
        "/", "/mnt/"
    ]
    if not run_cmd(rsync_cmd): return False

    log("5. Подготовка fstab...", "\033[96m")
    # Пытаемся получить UUID для надежной загрузки, если не выйдет — используем part
    try:
        uuid = subprocess.check_output(["blkid", "-s", "UUID", "-o", "value", part]).decode().strip()
        mount_point = f"UUID={uuid}"
    except Exception:
        mount_point = part

    with open("/mnt/etc/fstab", "w") as fst:
        fst.write(f"{mount_point}  /  ext4  errors=remount-ro  0  1\n")

    log("6. Установка GRUB...", "\033[96m")
    # --boot-directory это современная замена --root-directory
    if not run_cmd(["grub-install", "--boot-directory=/mnt/boot", disk]): 
        log("[-] Ошибка установки загрузчика GRUB!", "\033[91m")
        return False
    
    log("7. Генерация grub.cfg...", "\033[96m")
    os.makedirs("/mnt/boot/grub", exist_ok=True)
    
    # Динамический поиск ядра (зависит от того, как собирался Live Kit)
    kernel_path = "/vmlinuz"
    initrd_path = "/initrd.img"
    
    if os.path.exists("/mnt/boot/vmlinuz"): kernel_path = "/boot/vmlinuz"
    if os.path.exists("/mnt/boot/initrd.img"): initrd_path = "/boot/initrd.img"

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

    log("8. Очистка и размонтирование...", "\033[96m")
    run_cmd(["umount", "/mnt"])

    log("=== УСТАНОВКА ЗАВЕРШЕНА! МОЖНО ПЕРЕЗАГРУЖАТЬСЯ ===", "\033[92m")
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