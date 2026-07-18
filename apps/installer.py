import os
import sys
import subprocess
import glob

class SystemInstaller:
    """System Installer module for AetherOS (Legacy/MBR)"""
    
    requirements = []
    requirementsApt = ["parted", "e2fsprogs", "rsync"]

    def _log(self, text, color=""):
        print(f"{color}{text}\033[0m")
    
    def _run_cmd(self, cmd):
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            self._log(f"ERROR: {' '.join(cmd)}\n{res.stderr}", "\033[91m")
            return False
        return True

    def install_system(self, args):
        """install-system — Install AetherOS onto the local disk (/dev/sda)"""
        disk = "/dev/sda"
        part = f"{disk}1"
        
        self._log("=== AETHEROS INSTALLATION WIZARD (LEGACY/MBR) ===", "\033[93m")

        if not os.path.exists(disk):
            self._log(f"[-] Critical Error: Target disk {disk} not found!", "\033[91m")
            return False

        self._log("[*] Checking target disk state...", "\033[96m")
        try:
            check_fs = subprocess.run(["blkid", "-o", "value", "-s", "TYPE", part], 
                                      capture_output=True, text=True)
            is_installed = "ext4" in check_fs.stdout.strip()
        except Exception:
            is_installed = False

        if is_installed:
            self._log("\n[!] WARNING: AetherOS or another OS seems to be already installed on /dev/sda1!", "\033[91m")
            self._log("[!] Proceeding will completely ERASE all data on this disk!", "\033[91m")
            
            import asyncio
            try:
                confirm = input("Are you absolutely sure you want to reinstall? (yes/no): ").strip().lower()
            except Exception:
                confirm = "no"
                
            if confirm != "yes":
                self._log("[-] Installation aborted by user.", "\033[93m")
                return False

        self._log("\n0. Preparing live environment partitioning tools...", "\033[96m")
        self._run_cmd(["apt-get", "update", "-qq"])
        if not self._run_cmd(["apt-get", "install", "-y", "--no-install-recommends", "e2fsprogs", "parted", "rsync"]):
            self._log("[-] Warning: Failed to update live tools, trying to proceed with existing ones...", "\033[93m")

        self._log("1. Partitioning target disk (MBR/MSDOS)...", "\033[96m")
        if not self._run_cmd(["parted", "-s", disk, "mklabel", "msdos"]): return False
        if not self._run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "1MiB", "100%"]): return False
        if not self._run_cmd(["parted", "-s", disk, "set", "1", "boot", "on"]): return False

        self._log("2. Formatting partition to ext4...", "\033[96m")
        if not self._run_cmd(["mkfs.ext4", "-F", part]):
            self._log("[-] Error: Formatting failed! mkfs.ext4 might be missing.", "\033[91m")
            return False

        self._log("3. Mounting target partition...", "\033[96m")
        os.makedirs("/mnt", exist_ok=True)
        subprocess.run(["umount", "-l", "/mnt"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        if not self._run_cmd(["mount", part, "/mnt"]): 
            self._log("[-] Error: Failed to mount target partition!", "\033[91m")
            return False

        self._log("4. Copying system files (rsync)...", "\033[96m")
        rsync_cmd = [
            "rsync", "-aHAXx", 
            "--exclude=/proc/*", "--exclude=/sys/*", 
            "--exclude=/dev/*", "--exclude=/mnt/*", 
            "--exclude=/tmp/*", "--exclude=/run/*", 
            "/", "/mnt/"
        ]
        if not self._run_cmd(rsync_cmd): return False

        self._log("4.5. Deploying kernel from Live ISO image...", "\033[96m")
        os.makedirs("/mnt/boot", exist_ok=True)
        
        live_kernel = "/run/initramfs/memory/data/linux/boot/vmlinuz"
        if os.path.exists(live_kernel):
            self._log(f"[+] Found kernel image on ISO: {live_kernel}", "\033[92m")
            self._run_cmd(["cp", "-v", live_kernel, "/mnt/boot/vmlinuz-6.12.94+deb13-amd64"])
        else:
            self._log("[-] Critical Error: vmlinuz kernel not found on Live ISO!", "\033[91m")
            return False

        self._log("5. Generating /etc/fstab configuration...", "\033[96m")
        try:
            uuid = subprocess.check_output(["blkid", "-s", "UUID", "-o", "value", part]).decode().strip()
            mount_point = f"UUID={uuid}"
        except Exception:
            mount_point = part

        with open("/mnt/etc/fstab", "w") as fst:
            fst.write(f"{mount_point}  /  ext4  errors=remount-ro  0  1\n")

        self._log("5.5. Binding system dirs and updating chroot environment...", "\033[96m")
        self._run_cmd(["mount", "--bind", "/dev", "/mnt/dev"])
        self._run_cmd(["mount", "--bind", "/proc", "/mnt/proc"])
        self._run_cmd(["mount", "--bind", "/sys", "/mnt/sys"])
        self._run_cmd(["mount", "--bind", "/run", "/mnt/run"])

        if os.path.exists("/etc/resolv.conf"):
            self._run_cmd(["cp", "-L", "/etc/resolv.conf", "/mnt/etc/resolv.conf"])

        self._log("[*] Updating package index inside chroot...", "\033[96m")
        self._run_cmd(["chroot", "/mnt", "apt-get", "update"])
        
        self._log("[*] Installing grub-pc, os-prober, and initramfs-tools...", "\033[96m")
        apt_cmd = "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends grub-pc os-prober extlinux initramfs-tools"
        self._run_cmd(["chroot", "/mnt", "bash", "-c", apt_cmd])

        self._log("[*] Building custom initrd.img inside target system...", "\033[96m")
        gen_initrd_cmd = "update-initramfs -c -k 6.12.94+deb13-amd64"
        if not self._run_cmd(["chroot", "/mnt", "bash", "-c", gen_initrd_cmd]):
            self._log("[-] Warning: initrd generation failed! System might experience boot loop.", "\033[91m")
        else:
            self._log("[+] initrd.img generated successfully!", "\033[92m")

        self._log("6. Installing GRUB bootloader into MBR...", "\033[96m")
        chroot_grub = f"chroot /mnt grub-install {disk}"
        if not self._run_cmd(["bash", "-c", chroot_grub]):
            self._log("[-] Error: Failed to install GRUB bootloader into MBR!", "\033[91m")
            for p in ["/run", "/sys", "/proc", "/dev"]: self._run_cmd(["umount", "-l", f"/mnt{p}"])
            return False
            
        self._log("7. Generating grub.cfg config file...", "\033[96m")
        os.makedirs("/mnt/boot/grub", exist_ok=True)
        
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

        self._log("8. Cleaning up and unmounting directories...", "\033[96m")
        for p in ["/run", "/sys", "/proc", "/dev"]: 
            self._run_cmd(["umount", "-l", f"/mnt{p}"])
        self._run_cmd(["umount", "-l", "/mnt"])

        self._log("\n=== INSTALLATION SUCCESSFUL! YOU CAN NOW REBOOT YOUR SYSTEM ===", "\033[92m")
        return True