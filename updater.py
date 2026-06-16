import os
import sys
import requests
import zipfile
import tempfile
import shutil
import subprocess
from tkinter import messagebox

class SpatialUpdater:
    def __init__(self, current_version, repo_owner, repo_name):
        self.current_version = current_version
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        
    def download_icon_from_github(self):
        """Downloads the application icon from GitHub if missing locally."""
        icon_path = os.path.join(os.path.abspath("."), "Vunoxoulia.ico")
        if os.path.exists(icon_path):
            return icon_path

        try:
            icon_url = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/spatial-macro/Vunoxoulia.ico"
            response = requests.get(icon_url, timeout=5)
            if response.status_code == 200:
                with open(icon_path, 'wb') as f:
                    f.write(response.content)
                return icon_path
        except:
            pass
        return None

    def check_for_updates(self, silent=False):
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                raw_tag = data.get("tag_name", "0.0.0")
                latest_version = raw_tag.lower().replace("v", "")
                
                if self.is_newer(latest_version, self.current_version):
                    if messagebox.askyesno("Update Available", 
                        f"A new version ({latest_version}) is available!\n\n"
                        f"Current version: {self.current_version}\n"
                        f"Changes: {data.get('name', 'No description')}\n\n"
                        f"Do you want to download and install it?"):
                        return data.get("zipball_url"), latest_version
                elif not silent:
                    messagebox.showinfo("No Updates", f"You are already using the latest version ({self.current_version}).")
            else:
                if not silent:
                    messagebox.showerror("Error", f"Could not check for updates. GitHub returned: {response.status_code}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"An error occurred while checking for updates: {e}")
        return None, None

    def is_newer(self, latest, current):
        try:
            
            l_parts = [int(p) for p in latest.split(".")]
            c_parts = [int(p) for p in current.split(".")]
            
            
            max_len = max(len(l_parts), len(c_parts))
            l_parts.extend([0] * (max_len - len(l_parts)))
            c_parts.extend([0] * (max_len - len(c_parts)))
            
            return l_parts > c_parts
        except:
            return latest != current

    def install_update(self, download_url):
        try:
            
            response = requests.get(download_url, stream=True)
            if response.status_code != 200:
                messagebox.showerror("Error", "Failed to download update.")
                return

            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "update.zip")
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                
                extracted_folder = None
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isdir(item_path) and item != "__MACOSX":
                        extracted_folder = item_path
                        break
                
                if not extracted_folder:
                    messagebox.showerror("Error", "Update extraction failed.")
                    return

                
                
                
                dest_dir = os.path.abspath(".")
                
                for item in os.listdir(extracted_folder):
                    src_path = os.path.join(extracted_folder, item)
                    dest_path = os.path.join(dest_dir, item)
                    
                    if os.path.isdir(src_path):
                        if os.path.exists(dest_path):
                            shutil.rmtree(dest_path)
                        shutil.copytree(src_path, dest_path)
                    else:
                        shutil.copy2(src_path, dest_path)

                messagebox.showinfo("Success", "Update installed successfully! The application will now restart.")
                self.restart_app()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to install update: {e}")

    def restart_app(self):
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable])
            else:
                subprocess.Popen([sys.executable, "main.py"])
            os._exit(0)
        except:
            os._exit(0)
