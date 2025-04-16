import sys
import json
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMainWindow
from UserInterface import Ui_MainWindow
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import os

class RunCommandThread(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, command=""):
        super().__init__()
        self.command = command

    def set_command(self, command):
        self.command = command

    def run(self):
        process = subprocess.Popen(
            self.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.stdout:
            for line in process.stdout:
                self.output.emit(f"[stdout] {line.rstrip()}")

        if process.stderr:
            for line in process.stderr:
                self.output.emit(f"[stderr] {line.rstrip()}")

        process.wait()
        self.output.emit(f"\n[exit code] {process.returncode}")
        self.finished.emit(process.returncode)

class FrontendDeployment:
    def __init__(self, ui):
        self.ui = ui

        self.t_run_build = RunCommandThread()
        self.t_stop_server = RunCommandThread()
        self.t_zip_files = RunCommandThread()
        self.t_clean_up = RunCommandThread()
        self.t_transfer = RunCommandThread()
        self.t_unzip = RunCommandThread()
        self.t_start_server = RunCommandThread()

    def append_log(self, text):
        self.ui.logs.append(text)
        self.ui.logs.verticalScrollBar().setValue(self.ui.logs.verticalScrollBar().maximum())

    def log_command(self, command, password=None):
        """Logs the command to the UI logs, masking the password."""
        if password:
            command = command.replace(password, "******")  # Mask password if present
        self.append_log(f"Running command: {command}")
        print(f"Running command: {command}")  # Also print to console for debugging

    def run_build(self):
        frontend_dir = os.path.join(self.ui.local_folder.text(), 'frontend')
        command = f"cd {frontend_dir} && npm run-script build"
        self.log_command(command)  # Log command without password
        self.t_run_build.set_command(command)
        self.t_run_build.start()

    def stop_server(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        command = f"sshpass -p {password} ssh {server_ip} 'fuser -k 8002/tcp'"
        self.log_command(command, password)  # Log the command with password masking
        self.t_stop_server.set_command(command)
        self.t_stop_server.start()

    def zip_files(self):
        build_dir = os.path.join(self.ui.local_folder.text(), 'frontend')
        command = f"cd {build_dir} && zip -r build.zip build"
        self.log_command(command)  # Log command without password
        self.t_zip_files.set_command(command)
        self.t_zip_files.start()

    def clean_up(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        remote_folder = self.ui.remote_folder.text() + "frontend"

        command = (
            f"sshpass -p '{password}' ssh {server_ip} "
            f"\"cd {remote_folder} && "
            f"rm -rf build build.zip\""
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_clean_up.set_command(command)
        self.t_clean_up.start()

    def transfer(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        local_folder = self.ui.local_folder.text() + "frontend/"
        remote_folder = self.ui.remote_folder.text() + "frontend/"

        command = (
            f"sshpass -p '{password}' scp {local_folder}build.zip {server_ip}:{remote_folder}"
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_transfer.set_command(command)
        self.t_transfer.start()

    def unzip(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        remote_folder = self.ui.remote_folder.text() + "/frontend"

        command = (
            f"sshpass -p '{password}' ssh {server_ip} "
            f"\"cd {remote_folder} && unzip -o build.zip\""
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_unzip.set_command(command)
        self.t_unzip.start()

    def start_server(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        remote_folder = self.ui.remote_folder.text()

        command = (
            f"sshpass -p '{password}' ssh {server_ip} "
            f"\"source /root/miniconda3/etc/profile.d/conda.sh && "
            f"conda activate socialmediahub && "
            f"cd {remote_folder} && "
            f"bash run.sh\""
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_start_server.set_command(command)
        self.t_start_server.start()

    def deploy(self):
        print("Starting frontend deployment...")

        # Define the inner function to proceed to the next step
        def on_step_finished(next_step_method):
            # Get the last log line, if any
            last_log = self.ui.logs.toPlainText().strip().splitlines()[-1] if self.ui.logs.toPlainText().strip() else ""
            print(f"Checking last log: {last_log}")  # Debug print to inspect the last log

            # Check if the last log line starts with '[exit code]'
            if last_log.startswith("[exit code]"):
                # Check if the exit code is 0
                if "[exit code] 0" in last_log:
                    # Proceed to the next step in the pipeline
                    print(f"Last log was successful, proceeding to next step.")
                    next_step_method()
                else:
                    # Log the interruption and stop further deployment
                    self.ui.logs.append("Pipeline interrupted!")
                    print("Pipeline interrupted!")
                    # Do not proceed to the next step
                    self.stop_deployment()

        # Connect each step in the pipeline to the on_step_finished function
        self.t_run_build.finished.connect(lambda: on_step_finished(self.stop_server))
        self.t_stop_server.finished.connect(lambda: on_step_finished(self.zip_files))
        self.t_zip_files.finished.connect(lambda: on_step_finished(self.clean_up))
        self.t_clean_up.finished.connect(lambda: on_step_finished(self.transfer))
        self.t_transfer.finished.connect(lambda: on_step_finished(self.unzip))
        self.t_unzip.finished.connect(lambda: on_step_finished(self.start_server))
        self.t_start_server.finished.connect(lambda: print("Frontend deployment completed successfully!"))

        # Start the first step in the pipeline (run_build)
        self.run_build()

class BackendDeployment:
    def __init__(self, ui):
        self.ui = ui

        self.t_stop_server = RunCommandThread()
        self.t_zip_files = RunCommandThread()
        self.t_clean_up = RunCommandThread()
        self.t_transfer = RunCommandThread()
        self.t_unzip = RunCommandThread()
        self.t_start_server = RunCommandThread()

    def log_command(self, command, password=None):
        """Logs the command to the UI logs, masking the password."""
        if password:
            command = command.replace(password, "*********")  # Mask password if present
        self.ui.logs.append(f"Running: {command}")
        print(f"Running: {command}")  # Also print to console for debugging

    def stop_server(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        command = f"sshpass -p {password} ssh {server_ip} 'fuser -k 8002/tcp'"
        self.log_command(command, password)  # Log the command with password masking
        self.t_stop_server.set_command(command)
        self.t_stop_server.start()

    def zip_files(self):
        dir = os.path.join(self.ui.local_folder.text())
        command = f"cd {dir} && zip -r backend.zip backend"
        self.log_command(command)  # Log the command without password
        self.t_zip_files.set_command(command)
        self.t_zip_files.start()

    def clean_up(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        remote_folder = self.ui.remote_folder.text()  # No /frontend here

        command = (
            f"sshpass -p '{password}' ssh {server_ip} "
            f"\"cd {remote_folder} && "
            f"rm -rf backend backend.zip\""
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_clean_up.set_command(command)
        self.t_clean_up.start()

    def transfer(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        local_folder = self.ui.local_folder.text()  # Local folder where the backend files are
        remote_folder = self.ui.remote_folder.text()  # Remote folder on the server

        command = (
            f"sshpass -p '{password}' scp {local_folder}backend.zip {server_ip}:{remote_folder}"
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_transfer.set_command(command)
        self.t_transfer.start()

    def unzip(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        remote_folder = self.ui.remote_folder.text()  # Folder on the remote server where the zip file is

        command = (
            f"sshpass -p '{password}' ssh {server_ip} "
            f"\"cd {remote_folder} && unzip -o backend.zip\""
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_unzip.set_command(command)
        self.t_unzip.start()

    def start_server(self):
        password = self.ui.password.text()
        server_ip = self.ui.server_ip.text()
        remote_folder = self.ui.remote_folder.text()  # Should be something like ~/projects/humusmonitor

        command = (
            f"sshpass -p '{password}' ssh {server_ip} "
            f"\"source /root/miniconda3/etc/profile.d/conda.sh && "
            f"conda activate socialmediahub && "
            f"cd {remote_folder} && "
            f"bash run.sh\""
        )
        self.log_command(command, password)  # Log the command with password masking
        self.t_start_server.set_command(command)
        self.t_start_server.start()

    def deploy(self):
        print("Starting backend deployment...")

        # Define the inner function to proceed to the next step
        def on_step_finished(next_step_method):
            # Get the last log line, if any
            last_log = self.ui.logs.toPlainText().strip().splitlines()[-1] if self.ui.logs.toPlainText().strip() else ""
            print(f"Checking last log: {last_log}")  # Debug print to inspect the last log

            # Check if the last log line starts with '[exit code]'
            if last_log.startswith("[exit code]"):
                # Check if the exit code is 0
                if "[exit code] 0" in last_log:
                    # Proceed to the next step in the pipeline
                    print(f"Last log was successful, proceeding to next step.")
                    next_step_method()
                else:
                    # Log the interruption and stop further deployment
                    self.ui.logs.append("Pipeline interrupted!")
                    print("Pipeline interrupted!")
                
        # Connect each step in the pipeline to the on_step_finished function
        self.t_stop_server.finished.connect(lambda: on_step_finished(self.zip_files))
        self.t_zip_files.finished.connect(lambda: on_step_finished(self.clean_up))
        self.t_clean_up.finished.connect(lambda: on_step_finished(self.transfer))
        self.t_transfer.finished.connect(lambda: on_step_finished(self.unzip))
        self.t_unzip.finished.connect(lambda: on_step_finished(self.start_server))
        self.t_start_server.finished.connect(lambda: print("Backend deployment completed successfully!"))

        self.stop_server()

class App:
    def __init__(self, centalWidget, ui):
        self.ui = ui
        self.centalWidget = centalWidget

        self.last_pressed_button = None  # Track the last clicked button

        # Create deployment instances with clear names
        self.backend_deployment = BackendDeployment(ui)
        self.frontend_deployment = FrontendDeployment(ui)

        self.load_settings()
        self.make_connections()

    def highlight_button(self, button):
        # Reset the style of the last pressed button
        if self.last_pressed_button:
            self.last_pressed_button.setStyleSheet("")  # Reset the previous button style

        # Highlight the currently clicked button
        button.setStyleSheet("background-color: #a6d4fa; font-weight: bold;")
        self.last_pressed_button = button

    def append_log(self, text):
        self.ui.logs.append(text)
        self.ui.logs.verticalScrollBar().setValue(self.ui.logs.verticalScrollBar().maximum())

    def on_button_clicked(self, button, command):
        # Highlight the clicked button
        self.highlight_button(button)
        
        # Execute the command
        command()

    def make_connections(self):
        # Backend Deployment Buttons
        self.ui.stop_server_1.clicked.connect(lambda: self.on_button_clicked(self.ui.stop_server_1, self.stop_backend_deployment))
        self.ui.zip_1.clicked.connect(lambda: self.on_button_clicked(self.ui.zip_1, self.backend_deployment.zip_files))
        self.ui.clean_up_1.clicked.connect(lambda: self.on_button_clicked(self.ui.clean_up_1, self.backend_deployment.clean_up))
        self.ui.transfer_1.clicked.connect(lambda: self.on_button_clicked(self.ui.transfer_1, self.backend_deployment.transfer))
        self.ui.unzip_1.clicked.connect(lambda: self.on_button_clicked(self.ui.unzip_1, self.backend_deployment.unzip))
        self.ui.start_server_1.clicked.connect(lambda: self.on_button_clicked(self.ui.start_server_1, self.backend_deployment.start_server))

        # Frontend Deployment Buttons
        self.ui.run_build.clicked.connect(lambda: self.on_button_clicked(self.ui.run_build, self.frontend_deployment.run_build))
        self.ui.stop_server_2.clicked.connect(lambda: self.on_button_clicked(self.ui.stop_server_2, self.frontend_deployment.stop_server))
        self.ui.zip_2.clicked.connect(lambda: self.on_button_clicked(self.ui.zip_2, self.frontend_deployment.zip_files))
        self.ui.clean_up_2.clicked.connect(lambda: self.on_button_clicked(self.ui.clean_up_2, self.frontend_deployment.clean_up))
        self.ui.transfer_2.clicked.connect(lambda: self.on_button_clicked(self.ui.transfer_2, self.frontend_deployment.transfer))
        self.ui.unzip_2.clicked.connect(lambda: self.on_button_clicked(self.ui.unzip_2, self.frontend_deployment.unzip))
        self.ui.start_server_2.clicked.connect(lambda: self.on_button_clicked(self.ui.start_server_2, self.frontend_deployment.start_server))

        # Deploy All Button
        self.ui.deploy_backend.clicked.connect(lambda: self.on_button_clicked(self.ui.deploy_backend, self.backend_deployment.deploy))
        self.ui.deploy_frontend.clicked.connect(lambda: self.on_button_clicked(self.ui.deploy_frontend, self.frontend_deployment.deploy))

        # Backend Deployment Threads
        self.backend_deployment.t_stop_server.output.connect(self.append_log)
        self.backend_deployment.t_zip_files.output.connect(self.append_log)
        self.backend_deployment.t_clean_up.output.connect(self.append_log)
        self.backend_deployment.t_transfer.output.connect(self.append_log)
        self.backend_deployment.t_unzip.output.connect(self.append_log)
        self.backend_deployment.t_start_server.output.connect(self.append_log)

        # Frontend Deployment Threads
        self.frontend_deployment.t_run_build.output.connect(self.append_log)
        self.frontend_deployment.t_stop_server.output.connect(self.append_log)
        self.frontend_deployment.t_zip_files.output.connect(self.append_log)
        self.frontend_deployment.t_clean_up.output.connect(self.append_log)
        self.frontend_deployment.t_transfer.output.connect(self.append_log)
        self.frontend_deployment.t_unzip.output.connect(self.append_log)
        self.frontend_deployment.t_start_server.output.connect(self.append_log)

    def stop_backend_deployment(self):
        # Set parameters for backend deployment
        self.backend_deployment.password = self.ui.password.text()
        self.backend_deployment.remote_folder = self.ui.remote_folder.text()
        self.backend_deployment.ip_string = self.ui.server_ip.text()

        # Run stop_server
        self.backend_deployment.stop_server()

    def load_settings(self):
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)

                if 'server_ip' in settings:
                    self.ui.server_ip.setText(settings['server_ip'])
                if 'remote_folder' in settings:
                    self.ui.remote_folder.setText(settings['remote_folder'])
                if 'local_folder' in settings:
                    self.ui.local_folder.setText(settings['local_folder'])

        except (FileNotFoundError, json.JSONDecodeError):
            print("No settings file found or error in settings.json")

    def save_settings(self):
        settings = {
            'server_ip': self.ui.server_ip.text(),
            'remote_folder': self.ui.remote_folder.text(),
            'local_folder': self.ui.local_folder.text()
        }

        try:
            with open('settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            print("Settings saved successfully.")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def shut_down(self):
        self.save_settings()

class Main:
    def __init__(self):
        self.q_application = QtWidgets.QApplication(sys.argv)

        MainWindow = QtWidgets.QMainWindow()  # Create a window
        MainWindow.setWindowTitle("Deployment App")
        self.ui = Ui_MainWindow()  # Load the UI
        self.ui.setupUi(MainWindow)
        self.app = App(self.ui.centralwidget, self.ui)

        # MainWindow.show() and we show it directly
        MainWindow.show()

        self.q_application.exec_()
        self.app.shut_down()

    def make_connections(self):
        pass


if __name__ == "__main__":
    Main()
