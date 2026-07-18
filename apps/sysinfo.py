import os
import sys

class SysInfo:
    """System and Network monitoring utility for AetherOS"""
    
    # Packets required for AetherOS plugin manager
    requirements = ["rich"]
    requirementsApt = ["iputils-ping"]

    def info(self, args):
        """info — Display system architecture, hardware and uptime in fastfetch style"""
        try:
            from rich.console import Console
            from rich.columns import Columns
            from rich.panel import Panel
        except ImportError:
            print("Error: 'rich' library is not installed.")
            return

        console = Console()

        # 1. Fetch Uptime
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                uptime_str = f"{hours}h {minutes}m"
        except:
            uptime_str = "Unknown"

        # 2. Fetch RAM Info
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
                total = int(lines[0].split()[1]) // 1024
                free = int(lines[1].split()[1]) // 1024
                # Simplistic approach, ignoring buffers/cached for layout cleanliness
                used = total - free
                ram_str = f"{used} MB / {total} MB"
        except:
            ram_str = "Unknown"

        # 3. Fetch CPU Info (Model Name)
        cpu_model = "Unknown Processor"
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        # Shorten if too long for clean fetch look
                        if len(cpu_model) > 30:
                            cpu_model = cpu_model[:27] + "..."
                        break
        except:
            pass

        # ASCII Art for AetherOS
        ascii_logo = (
            "[bold cyan]"
            "   /\   |  | |_  \n"
            "  /  \  |--| |--  \n"
            " /____\ |  | |___ \n"
            "   __   ____  ____\n"
            "  /  \  |___  |   \n"
            "  \__/   ___| |___"
            "[/bold cyan]"
        )

        # Fastfetch-style stats block
        fetch_stats = (
            f"[bold cyan]OS:[/bold cyan] AetherOS\n"
            f"[bold cyan]Kernel:[/bold cyan] Linux 6.12.94+deb13-amd64\n"
            f"[bold cyan]Uptime:[/bold cyan] {uptime_str}\n"
            f"[bold cyan]CPU:[/bold cyan] {cpu_model}\n"
            f"[bold cyan]Memory:[/bold cyan] {ram_str}\n"
            f"[bold cyan]Shell:[/bold cyan] Python Environment"
        )

        # Render side-by-side using Columns
        logo_panel = Panel(ascii_logo, expand=False, border_style="cyan")
        stats_panel = Panel(fetch_stats, title="[bold white]System Info[/bold white]", expand=False, border_style="magenta")

        console.print(Columns([logo_panel, stats_panel]))

    def ping(self, args):
        """ping [host] — Test network connection using ICMP packets (default: 1.1.1.1)"""
        import subprocess

        host = args[0] if args else "1.1.1.1"
        print(f"[*] Sending ICMP packets to {host}...")
        
        try:
            res = subprocess.run(
                ["ping", "-c", "3", "-W", "2", host], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                timeout=5
            )
            
            if res.returncode == 0:
                print("[+] Network is reachable! Stats summary:")
                stats = [line for line in res.stdout.splitlines() if "rtt" in line or "min/avg/max" in line]
                if stats:
                    print(stats[0])
                else:
                    print("Packets transmitted successfully.")
            else:
                print(f"[-] Error: Host {host} is unreachable (Exit code: {res.returncode}).")
                if res.stderr:
                    print(f"Details: {res.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            print("[-] Error: Request timed out.")
        except Exception as e:
            print(f"[-] Error executing ping command: {e}")

    def _internal_helper(self):
        """Internal method, hidden from the command manager loop"""
        return "Internal method, hidden from user"