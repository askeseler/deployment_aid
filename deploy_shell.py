import subprocess
import threading

def run_command(command: str):
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    def monitor_output():
        if process.stdout:
            for line in process.stdout:
                print("[stdout]", line, end='')
        if process.stderr:
            for line in process.stderr:
                print("[stderr]", line, end='')

    monitor_thread = threading.Thread(target=monitor_output)
    monitor_thread.start()

    process.wait()
    monitor_thread.join()
    print(f"\n[exit code] {process.returncode}")

if __name__ == "__main__":
    cmd = input("Enter your shell command: ")
    run_command(cmd)

