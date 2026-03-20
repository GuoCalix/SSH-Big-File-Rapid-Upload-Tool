import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import paramiko
from scp import SCPClient

class ScpGui:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH 极速上传工具 (支持密码/私钥)")
        self.root.geometry("500x520")
        
        self.config_path = os.path.expanduser(r"~\.ssh\config")
        self.hosts = self.parse_ssh_config()

        # UI 布局
        tk.Label(root, text="1. 选择服务器 (SSH Config):", font=('Arial', 10, 'bold')).pack(pady=5)
        self.host_combo = ttk.Combobox(root, values=list(self.hosts.keys()), state="readonly", width=45)
        self.host_combo.pack(pady=5)

        tk.Label(root, text="2. 选择本地文件:", font=('Arial', 10, 'bold')).pack(pady=5)
        self.local_path_var = tk.StringVar()
        tk.Entry(root, textvariable=self.local_path_var, width=50).pack(padx=20)
        tk.Button(root, text="浏览文件", command=self.select_file).pack(pady=5)

        tk.Label(root, text="3. 远程目标路径:", font=('Arial', 10, 'bold')).pack(pady=5)
        self.remote_path_var = tk.StringVar(value="/tmp/")
        tk.Entry(root, textvariable=self.remote_path_var, width=50).pack(padx=20)

        # 进度条
        tk.Label(root, text="传输进度:", font=('Arial', 9)).pack(pady=(20, 0))
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)
        self.pct_label = tk.Label(root, text="0%", fg="blue")
        self.pct_label.pack()

        self.upload_btn = tk.Button(root, text="🚀 开始上传", bg="#0078D7", fg="white", 
                                   font=('Arial', 11, 'bold'), height=2, width=20, command=self.start_upload_thread)
        self.upload_btn.pack(pady=20)

        self.status_label = tk.Label(root, text="就绪", fg="gray")
        self.status_label.pack()

    def parse_ssh_config(self):
        hosts = {}
        if not os.path.exists(self.config_path): return hosts
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                current_host = None
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if line.lower().startswith("host "):
                        current_host = line.split()[1]
                        hosts[current_host] = {}
                    elif current_host:
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            hosts[current_host][parts[0].lower()] = parts[1].strip('"')
        except Exception: pass
        return hosts

    def select_file(self):
        path = filedialog.askopenfilename()
        if path: self.local_path_var.set(path)

    def progress_callback(self, filename, size, sent):
        percentage = float(sent) / float(size) * 100
        self.root.after(0, self.update_ui_progress, percentage)

    def update_ui_progress(self, val):
        self.progress['value'] = val
        self.pct_label.config(text=f"{val:.1f}%")

    def start_upload_thread(self):
        if not self.host_combo.get() or not self.local_path_var.get():
            messagebox.showwarning("提示", "请选择服务器和文件")
            return
        self.upload_btn.config(state="disabled")
        self.status_label.config(text="正在连接...", fg="blue")
        self.progress['value'] = 0
        t = threading.Thread(target=self.execute_upload)
        t.daemon = True
        t.start()

    def execute_upload(self):
        host_alias = self.host_combo.get()
        conf = self.hosts[host_alias]
        local_file = self.local_path_var.get()
        remote_path = self.remote_path_var.get()
        
        if remote_path.endswith('/'):
            remote_path += os.path.basename(local_file)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        hostname = conf.get('hostname')
        port = int(conf.get('port', 22))
        user = conf.get('user', 'root')
        key_path = conf.get('identityfile')
        if key_path: key_path = os.path.expanduser(key_path)

        try:
            # 1. 尝试使用私钥连接 (如果 config 里有 IdentityFile 且文件存在)
            if key_path and os.path.exists(key_path):
                try:
                    ssh.connect(hostname, port=port, username=user, key_filename=key_path, timeout=10)
                except (paramiko.PasswordRequiredException, paramiko.AuthenticationException):
                    # 如果私钥需要密码或私钥失效，弹出密码框
                    pwd = self.ask_password(f"服务器 {host_alias} 认证失败或私钥加密，请输入密码:")
                    if not pwd: raise Exception("用户取消了密码输入")
                    ssh.connect(hostname, port=port, username=user, password=pwd, key_filename=key_path)
            else:
                # 2. 如果没有私钥配置，直接请求手动输入密码
                pwd = self.ask_password(f"未发现私钥。请输入 {user}@{host_alias} 的登录密码:")
                if not pwd: raise Exception("未提供密码")
                ssh.connect(hostname, port=port, username=user, password=pwd)

            # 执行上传
            with SCPClient(ssh.get_transport(), progress=self.progress_callback) as scp:
                scp.put(local_file, remote_path)
            
            self.root.after(0, lambda: messagebox.showinfo("成功", "文件上传完成！"))
            self.root.after(0, lambda: self.status_label.config(text="完成", fg="green"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("传输错误", str(e)))
            self.root.after(0, lambda: self.status_label.config(text="失败", fg="red"))
        finally:
            ssh.close()
            self.root.after(0, lambda: self.upload_btn.config(state="normal"))

    def ask_password(self, prompt):
        # 必须在主线程弹出对话框
        return simpledialog.askstring("SSH 认证", prompt, show='*')

if __name__ == "__main__":
    root = tk.Tk()
    app = ScpGui(root)
    root.mainloop()