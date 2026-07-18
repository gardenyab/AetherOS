import os
import subprocess
import shutil
import sys

def update_system():
    project_path = "/root"
    print(f"\n[!] Checking for updates...")

    if not os.path.exists(os.path.join(project_path, ".git")):
        print("[-] Error: Not a git repository!")
        return

    try:
        subprocess.run(["git", "-C", project_path, "fetch", "origin"], 
                       check=True, capture_output=True)
        
        local = subprocess.check_output(["git", "-C", project_path, "rev-parse", "HEAD"]).decode().strip()
        remote = subprocess.check_output(["git", "-C", project_path, "rev-parse", "origin/main"]).decode().strip()
        
        if local == remote:
            print("[+] System is already up to date.")
            return

        print("[!] Updates found. Applying...")

        subprocess.run(["git", "-C", project_path, "reset", "--hard", "origin/main"], check=True)
        
        print("[+] System updated successfully!")
        print("[!] Restarting shell to apply changes...")
        
        os.execv(sys.executable, ['python3'] + sys.argv)

    except subprocess.CalledProcessError as e:
        print(f"[-] Update failed: {e.stderr.decode() if e.stderr else 'Unknown error'}")
    except Exception as e:
        print(f"[-] Unexpected error: {e}")

def show_menu():
    while True:
        os.system('clear')
        
        free_space = shutil.disk_usage('/').free // (1024**2)
        
        print("================================")
        print("      WELCOME AETHER OS         ")
        print("================================")
        print(f"  RAM/DISK (approx): {free_space} MB")
        print("--------------------------------")
        print("  1) Install")
        print("  2) Shutdown")
        print("  3) Update")
        print("  q) Exit")
        print("================================")
        
        choice = input("Select an option: ").strip().lower()
        
        if choice == '1':
            print("\nStarting installer...")
            subprocess.run(["python3", "/root/installer.py"])
            input("\nInstaller finished. Press Enter to return to menu...")
            
        elif choice == '2':
            print("\nShutting down...")
            subprocess.run(["poweroff"])
        
        elif choice == '3':
            update_system()
            input("\nPress Enter to return to menu...")
            
        elif choice == 'q':
            print("Exiting shell...")
            break

if __name__ == "__main__":
    if os.isatty(sys.stdin.fileno()):
        show_menu()
    else:
        print("Error: Not a TTY")