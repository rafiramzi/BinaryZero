import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import sys

def select_file():
    file_path.set(filedialog.askopenfilename(filetypes=[("Python files", "*.py")]))

def build():
    script = file_path.get()
    target_os = os_choice.get()

    if not script:
        messagebox.showerror("Error", "Please select a Python script.")
        return

    cmd = ["pyinstaller", "--onefile"]

    if target_os == "Windows (.exe)":
        if sys.platform != "win32":
            messagebox.showwarning("Warning", "Cross-compiling for Windows must be done on Windows.")
            return
        cmd.append("--windowed")  # Hides terminal

    elif target_os == "macOS (.app)":
        if sys.platform != "darwin":
            messagebox.showwarning("Warning", "Cross-compiling for macOS must be done on macOS.")
            return
        cmd.append("--windowed")  # Hides terminal

    elif target_os == "Linux App":
        if sys.platform != "linux":
            messagebox.showwarning("Warning", "Cross-compiling for Linux must be done on Linux.")
            return
        # No --windowed on Linux (optional)

    cmd.append(script)

    # Run PyInstaller
    try:
        subprocess.run(cmd, check=True)
        dist_dir = os.path.join(os.getcwd(), "dist")
        messagebox.showinfo("Success", f"Build complete!\nCheck the dist/ folder:\n{dist_dir}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Build Failed", f"PyInstaller error:\n{e}")

# GUI Setup
app = tk.Tk()
app.title("Payload Converter by BinaryZero")
app.geometry("500x250")
app.resizable(False, False)

file_path = tk.StringVar()
os_choice = tk.StringVar(value="Windows (.exe)")

tk.Label(app, text="Select Python script (.py):").pack(pady=10)
tk.Entry(app, textvariable=file_path, width=50).pack(padx=10)
tk.Button(app, text="Browse", command=select_file).pack(pady=5)

tk.Label(app, text="Target Platform:").pack(pady=10)
ttk.Combobox(app, textvariable=os_choice, values=["Windows (.exe)", "macOS (.app)", "Linux App"], state="readonly").pack()

tk.Button(app, text="Build", command=build, bg="green", fg="white").pack(pady=20)

app.mainloop()
