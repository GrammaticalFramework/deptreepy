import subprocess
import shutil
import os

FRONTEND_DIR = "frontend"
BACKEND_STATIC_DIR = "./static"

print("🏗️  Building frontend using Vite...")
subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)
subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)

print("🧹 Cleaning old static files...")
shutil.rmtree(BACKEND_STATIC_DIR, ignore_errors=True)
os.makedirs(BACKEND_STATIC_DIR, exist_ok=True)

print("📦 Copying built files to ./static...")
dist_path = os.path.join(FRONTEND_DIR, "dist")
for item in os.listdir(dist_path):
    s = os.path.join(dist_path, item)
    d = os.path.join(BACKEND_STATIC_DIR, item)
    if os.path.isdir(s):
        shutil.copytree(s, d)
    else:
        shutil.copy2(s, d)

print(f"✅ Done: Frontend deployed to {BACKEND_STATIC_DIR}")
