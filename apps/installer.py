import subprocess
import os
import shutil
import sys
import time


class Installler:
    def _log(self, text, color=""):
    # Цвета для терминала (опционально)
        print(f"{color}{text}\033[0m")
    
    def _run_cmd(self, cmd):
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(res.stderr)
            self._log(f"ОШИБКА: {' '.join(cmd)}\n{res.stderr}", "\033[91m")
            return False
        return True

    def do_install(self, args):
        disk = "/dev/sda"
        self._log("=== НАЧАЛО УСТАНОВКИ (LEGACY/MBR) ===", "\033[93m")
        part = f"{disk}1"

        if not os.path.exists(disk):
            self._log(f"[-] Ошибка: Диск {disk} не найден!", "\033[91m")
            return False

        self._log("1. Разметка диска (MBR)...", "\033[96m")
        if not self._run_cmd(["parted", "-s", disk, "mklabel", "msdos"]): return False
        if not self._run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "1MiB", "100%"]): return False
        if not self._run_cmd(["parted", "-s", disk, "set", "1", "boot", "on"]): return False

        self._log("2. Форматирование в ext4...", "\033[96m")
        if not self._run_cmd(["mkfs.ext4", "-F", part]):
            self._log("[-] Ошибка форматирования!", "\033[91m")
            return False

        self._log("3. Монтирование...", "\033[96m")
        os.makedirs("/mnt", exist_ok=True)
        
        # Безопасное размонтирование без ломающих флагов
        subprocess.run(["umount", "-l", "/mnt"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        
        if not self._run_cmd(["mount", part, "/mnt"]): 
            self._log("[-] Ошибка монтирования раздела!", "\033[91m")
            return False

        self._log("4. Копирование файлов (rsync)...", "\033[96m")
        rsync_cmd = [
            "rsync", "-aHAXx", 
            "--exclude=/proc/*", "--exclude=/sys/*", 
            "--exclude=/dev/*", "--exclude=/mnt/*", 
            "--exclude=/tmp/*", "--exclude=/run/*", 
            "/", "/mnt/"
        ]
        if not self._run_cmd(rsync_cmd): return False

        self._log("4.5. Извлечение ядра и initrd с CD-ROM...", "\033[96m")
        os.makedirs("/tmp/cdrom", exist_ok=True)
        os.makedirs("/mnt/boot", exist_ok=True)
        
        # Перебираем возможные устройства CD-ROM в QEMU
        cd_mounted = False
        for cd_dev in ["/dev/sr0", "/dev/cdrom"]:
            # Принудительно отмонтируем перед попыткой
            subprocess.run(["umount", "-l", "/tmp/cdrom"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            if self._run_cmd(["mount", "-o", "ro", cd_dev, "/tmp/cdrom"]):
                cd_mounted = True
                break
                
        if cd_mounted:
            import glob
            # Ищем ядро и initrd в стандартных для Live-ISO путях (/boot или /live)
            cd_kernels = glob.glob("/tmp/cdrom/boot/vmlinuz*") + glob.glob("/tmp/cdrom/live/vmlinuz*")
            cd_initrds = glob.glob("/tmp/cdrom/boot/initrd*") + glob.glob("/tmp/cdrom/live/initrd*")
            
            if cd_kernels:
                self._log(f"[+] Найдено ядро на CD: {cd_kernels[0]}", "\033[92m")
                self._run_cmd(["cp", "-v", cd_kernels[0], "/mnt/boot/vmlinuz-6.12.94+deb13-amd64"])
            else:
                self._log("[-] Ядро на CD-ROM не обнаружено!", "\033[91m")

            if cd_initrds:
                self._log(f"[+] Найден initrd на CD: {cd_initrds[0]}", "\033[92m")
                self._run_cmd(["cp", "-v", cd_initrds[0], "/mnt/boot/initrd.img-6.12.94+deb13-amd64"])
            else:
                self._log("[-] Initrd на CD-ROM не обнаружен!", "\033[91m")
                
            self._run_cmd(["umount", "/tmp/cdrom"])
        else:
            self._log("[-] Не удалось примонтировать CD-ROM! Файлы ядра могут отсутствовать.", "\033[91m")

        self._log("5. Подготовка fstab...", "\033[96m")
        try:
            uuid = subprocess.check_output(["blkid", "-s", "UUID", "-o", "value", part]).decode().strip()
            mount_point = f"UUID={uuid}"
        except Exception:
            mount_point = part

        with open("/mnt/etc/fstab", "w") as fst:
            fst.write(f"{mount_point}  /  ext4  errors=remount-ro  0  1\n")

        self._log("6. Установка GRUB (через chroot)...", "\033[96m")
        
        # Монтируем виртуальные ФС для корректного инсталла GRUB внутри окружения
        self._run_cmd(["mount", "--bind", "/dev", "/mnt/dev"])
        self._run_cmd(["mount", "--bind", "/proc", "/mnt/proc"])
        self._run_cmd(["mount", "--bind", "/sys", "/mnt/sys"])
        self._run_cmd(["mount", "--bind", "/run", "/mnt/run"])

        chroot_grub = f"chroot /mnt grub-install {disk}"
        if not self._run_cmd(["bash", "-c", chroot_grub]):
            self._log("[-] Ошибка установки загрузчика GRUB в MBR!", "\033[91m")
            for p in ["/run", "/sys", "/proc", "/dev"]: self._run_cmd(["umount", "-l", f"/mnt{p}"])
            return False
            
        for p in ["/run", "/sys", "/proc", "/dev"]: 
            self._run_cmd(["umount", "-l", f"/mnt{p}"])
        
        self._log("7. Генерация grub.cfg...", "\033[96m")
        os.makedirs("/mnt/boot/grub", exist_ok=True)
        
        import glob
        
        vmlinuz_files = glob.glob("/mnt/boot/vmlinuz-*")
        initrd_files = glob.glob("/mnt/boot/initrd.img-*")
        
        kernel_path = vmlinuz_files[0].replace("/mnt", "") if vmlinuz_files else "/boot/vmlinuz-6.12.94+deb13-amd64"
        initrd_path = initrd_files[0].replace("/mnt", "") if initrd_files else "/boot/initrd.img-6.12.94+deb13-amd64"

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

        self._log("8. Очистка и размонтирование...", "\033[96m")
        self._run_cmd(["umount", "-l", "/mnt"])

        self._log("=== УСТАНОВКА ЗАВЕРШЕНА! МОЖНО ПЕРЕЗАГРУЖАТЬСЯ ===", "\033[92m")
        return True