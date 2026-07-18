import os
import subprocess
import shutil
import sys

def show_menu():
    while True:
        os.system('clear')
        
        free_space = shutil.disk_usage('/').free // (1024**2)
        
        print("================================")
        print("      WELCOME PYTHON OS         ")
        print("================================")
        print(f"  RAM/DISK (approx): {free_space} MB")
        print("--------------------------------")
        print("  1) Install")
        print("  2) Shutdown")
        print("  q) Exit")
        print("================================")
        
        choice = input("Select an option: ").strip().lower()
        
        if choice == '1':
            print("\nStarting installer...")
            # Запускаем инсталлер
            subprocess.run(["python3", "/root/installer.py"])
            input("\nInstaller finished. Press Enter to return to menu...")
            
        elif choice == '2':
            print("\nShutting down...")
            subprocess.run(["poweroff"])
            
        elif choice == 'q':
            print("Exiting shell...")
            break

if __name__ == "__main__":
    if os.isatty(sys.stdin.fileno()):
        show_menu()
    else:
        print("Error: Not a TTY")