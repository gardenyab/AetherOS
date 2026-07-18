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
import config as cfg
import core

def show_help():
    core.load_apps()
    print(f"\n              AETHER OS v{cfg.VERSION} — COMMAND REFERENCE")
    print("====================================================")
    print("📦 Built-in System Commands:")
    print("  ↳ install <url>    - Download and install .py module")
    print("  ↳ uninstall <name> - Remove installed module")
    print("  ↳ update           - Fetch and apply updates from Git")
    print("  ↳ shutdown         - Shutdown system")
    print("  ↳ help             - Show this help")
    print("  ↳ clear            - Clear screen")
    print("  ↳ exit / q         - Exit shell")
    
    if not core.MODULES:
        print("\n📦 No modules found in ./apps/")
    else:
        for module in core.MODULES:
            class_name = module.__class__.__name__.lower()
            class_doc = module.__class__.__doc__ or "No description"
            print(f"\n📦 Module: {class_name} ({class_doc})")
            for name, method in inspect.getmembers(module, predicate=inspect.ismethod):
                if not name.startswith('_'):
                    doc = method.__doc__ or "No description"
                    print(f"  ↳ {name:<12} - {doc.strip().split('\n')[0]}")
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
            print("[+] System is up to date.")
            return
        print("[!] Updates found. Applying...")
        subprocess.run(["git", "-C", project_path, "reset", "--hard", "origin/main"], check=True)
        print("[+] System updated successfully!\n[!] Restarting shell...")
        os.execv(sys.executable, ['python3'] + sys.argv)
    except Exception as e:
        print(f"[-] Update failed: {e}")

def start_shell():
    os.system('clear')
    core.load_apps()
    readline.set_history_length(100)
    
    def completer(text, state):
        builtins = ['help', 'clear', 'install', 'uninstall', 'install-system', 'update', 'shutdown', 'exit', 'q']
        app_cmds = []
        for module in core.MODULES:
            app_cmds.extend([name for name, _ in inspect.getmembers(module, inspect.ismethod) if not name.startswith('_')])
        options = [cmd for cmd in (builtins + app_cmds) if cmd.startswith(text)]
        return options[state] if state < len(options) else None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    
    print(f"AetherOS v{cfg.VERSION}")
    print("~ Commands: help, clear, install, update, uninstall, shutdown")
    
    while True:
        try:
            user_input = input("user@AetherOS # ").strip()
            if not user_input: continue
                
            parts = user_input.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd == 'help':
                show_help()
            elif cmd == 'clear':
                os.system('clear')
            elif cmd == 'install':
                core.download_app(args[0] if args else None)
            elif cmd == 'uninstall':
                core.delete_app(args[0] if args else None)
            elif cmd == 'update':
                update_system()
                input("\nPress Enter to continue...")
            elif cmd == 'shutdown':
                print("\nShutting down...")
                subprocess.run(["poweroff"])
            elif cmd in ['exit', 'q']:
                print("Exiting Aether OS...")
                break
            else:
                command_found = False
                for module in core.MODULES:
                    if hasattr(module, cmd):
                        method = getattr(module, cmd)
                        if inspect.ismethod(method) and not cmd.startswith('_'):
                            method(args)
                            command_found = True
                            break
                if not command_found:
                    print(f"Error: Command '{cmd}' not found. Type 'help'.")
        except (KeyboardInterrupt, EOFError):
            print("\nUse 'exit' or 'q' to quit.")

if __name__ == "__main__":
    if os.isatty(sys.stdin.fileno()):
        start_shell()
    else:
        print("Error: Not a TTY")