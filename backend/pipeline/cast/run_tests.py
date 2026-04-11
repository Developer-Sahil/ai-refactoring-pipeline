from cast.pipeline import run
import os

os.makedirs("output", exist_ok=True)

files = [
    ("cast/tests/order_service.py",  "output/out_python.json"),
    ("cast/tests/cart.js",           "output/out_js.json"),
    ("cast/tests/user-service.ts",   "output/out_ts.json"),
    ("cast/tests/payment.go",        "output/out_go.json"),
    ("cast/tests/user.rs",           "output/out_rust.json"),
    ("cast/tests/auth.rb",           "output/out_ruby.json"),
    ("cast/tests/mailer.php",        "output/out_php.json"),
]

print("Running cAST pipeline tests...\n" + "-"*30)
for src, out in files:
    if not os.path.exists(src):
        print(f"[!] Warning: Test file not found: {src}")
        continue
    try:
        path = run(src, out, verbose=True)
        print(f"[PASS] Successfully processed {src} -> {path}\n")
    except Exception as e:
        print(f"[FAIL] Failed processing {src}: {e}\n")
