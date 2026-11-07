import os
import sys
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
        from settings import get_app_path
        icon_path = os.path.join(get_app_path(), "Vunoxoulia.ico")
        if os.path.exists(icon_path):
            return icon_path

        try:
            import requests
            icon_url = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/app/Vunoxoulia.ico"
            response = requests.get(icon_url, timeout=5)
            if response.status_code == 200:
                with open(icon_path, 'wb') as f:
                    f.write(response.content)
                return icon_path
        except:
            pass
        return None

    def check_for_updates(self, silent=False):
        import requests
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

    def _download(self, url, path, tries=3):
        import requests
        why = "unknown error"
        for attempt in range(1, tries + 1):
            try:
                with requests.get(url, stream=True, timeout=(10, 60)) as r:
                    if r.status_code != 200:
                        why = f"GitHub answered {r.status_code}"
                        continue
                    expected = int(r.headers.get("Content-Length") or 0)
                    got = 0
                    with open(path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                got += len(chunk)
                if expected and got != expected:
                    why = f"download cut off ({got} of {expected} bytes)"
                    continue
                with zipfile.ZipFile(path) as z:
                    bad = z.testzip()
                    if bad:
                        why = f"damaged file in the download: {bad}"
                        continue
                return None
            except (requests.RequestException, zipfile.BadZipFile, OSError) as e:
                why = f"{type(e).__name__}: {e}"
        return why

    @staticmethod
    def _program_ok(folder):
        if not os.path.exists(os.path.join(folder, "main.py")):
            return "main.py is missing"
        for root, _, files in os.walk(folder):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "rb") as fh:
                            src = fh.read()
                        if b"\0" in src:
                            return f"{f} is damaged"
                        compile(src, path, "exec")
                    except (SyntaxError, ValueError, OSError):
                        return f"{f} is damaged"
        return None

    def install_update(self, download_url):
        from settings import get_root_path
        dest_dir = get_root_path()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "update.zip")
                why = self._download(download_url, zip_path)
                if why:
                    messagebox.showerror("Update", f"The download didn't come through properly ({why}).\n\n"
                                                   "Nothing was changed - try again later.")
                    return
                unpack = os.path.join(temp_dir, "unpacked")
                with zipfile.ZipFile(zip_path) as z:
                    z.extractall(unpack)
                folders = [os.path.join(unpack, d) for d in os.listdir(unpack)
                           if os.path.isdir(os.path.join(unpack, d)) and d != "__MACOSX"]
                src_root = folders[0] if len(folders) == 1 else unpack
                new_app = os.path.join(src_root, "app")
                why = self._program_ok(new_app) if os.path.isdir(new_app) else "no app folder in the download"
                if why:
                    messagebox.showerror("Update", f"The update looks incomplete ({why}).\n\nNothing was changed.")
                    return

                app_dir = os.path.join(dest_dir, "app")
                staged, old = app_dir + ".new", app_dir + ".old"
                for d in (staged, old):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(new_app, staged, ignore=shutil.ignore_patterns("__pycache__"))
                why = self._program_ok(staged)
                if why:
                    shutil.rmtree(staged, ignore_errors=True)
                    messagebox.showerror("Update", f"Copying the update failed ({why}).\n\nNothing was changed.")
                    return
                try:
                    os.replace(app_dir, old)
                    try:
                        os.replace(staged, app_dir)
                    except OSError:
                        os.replace(old, app_dir)
                        raise
                except OSError:
                    shutil.copytree(staged, app_dir, dirs_exist_ok=True)
                    shutil.rmtree(staged, ignore_errors=True)
                shutil.rmtree(old, ignore_errors=True)

                for item in os.listdir(src_root):
                    src, dst = os.path.join(src_root, item), os.path.join(dest_dir, item)
                    if item in ("app", "data", ".launcher", ".git") or item.startswith("."):
                        continue
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        if item.lower().endswith(".bat") and os.path.exists(dst):
                            with open(src, "rb") as a, open(dst, "rb") as b:
                                if a.read() == b.read():
                                    continue
                        shutil.copy2(src, dst)

                messagebox.showinfo("Success", "Update installed successfully! The application will now restart.")
                self.restart_app()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to install update: {e}\n\nIf the macro doesn't start, download it "
                                          "again from GitHub and copy your old data folder into the new one.")

    def restart_app(self):
        try:
            from settings import flush_all
            flush_all()
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable])
            else:
                from settings import get_app_path, get_root_path
                launcher = os.path.join(get_root_path(), "Windows_Launcher.bat")
                if os.path.exists(launcher):
                    subprocess.Popen(["cmd", "/c", "start", "", launcher], cwd=get_root_path())
                else:
                    subprocess.Popen([sys.executable, os.path.join(get_app_path(), "main.py")], cwd=get_root_path())
            os._exit(0)
        except:
            os._exit(0)