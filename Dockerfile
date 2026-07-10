FROM gozargah/marzban:latest

ARG XRAY_VERSION=v26.3.27

RUN apt-get update && \
    apt-get install -y --no-install-recommends unzip curl && \
    curl -sL -o /tmp/xray.zip "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" && \
    mkdir -p /usr/local/share/xray-core && \
    unzip -o /tmp/xray.zip -d /usr/local/share/xray-core && \
    chmod +x /usr/local/share/xray-core/xray && \
    rm /tmp/xray.zip && \
    apt-get purge -y unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV XRAY_EXECUTABLE_PATH=/usr/local/share/xray-core/xray
ENV XRAY_ASSETS_PATH=/usr/local/share/xray-core

# Marzban's x25519 output parser only understands the old
# "Private key: X\nPublic key: Y" format. Newer Xray-core releases
# changed this to "PrivateKey: X\nPassword (PublicKey): Y", which crashes
# Marzban on startup. Patch the parser to accept both formats.
RUN python3 - <<'PYEOF'
path = "/code/app/xray/core.py"
with open(path) as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "re.match" in line and "Private key" in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines[i] = (
            indent
            + "m = re.search(r'Private ?[Kk]ey:\\s*(\\S+).*?"
            + "(?:Public ?[Kk]ey|Password ?\\(PublicKey\\))\\s*:\\s*(\\S+)', "
            + "output, re.DOTALL)\n"
        )
        break
with open(path, "w") as f:
    f.writelines(lines)
PYEOF

# Marzban has no built-in way to serve arbitrary static files (e.g. a logo
# used by a custom subscription page template). Mount /var/lib/marzban/assets
# (already volume-mounted) at /assets so it's served with proper Cache-Control
# / ETag headers instead of inlining assets as base64 in the template.
RUN python3 - <<'PYEOF'
path = "/code/app/__init__.py"
with open(path) as f:
    content = f.read()

marker = "app.include_router(api_router)\n"
addition = (
    "\nfrom fastapi.staticfiles import StaticFiles  # noqa\n"
    "import os as _os  # noqa\n"
    "if _os.path.isdir('/var/lib/marzban/assets'):\n"
    "    app.mount('/assets', StaticFiles(directory='/var/lib/marzban/assets'), name='custom_assets')\n"
)
assert marker in content, "include_router marker not found"
content = content.replace(marker, marker + addition, 1)

with open(path, "w") as f:
    f.write(content)
PYEOF
