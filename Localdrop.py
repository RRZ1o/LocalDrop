#!/usr/bin/env python3
import os
import re
import json
import time
import html
import hashlib
import secrets
import mimetypes
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = Path(os.environ.get("RRZ1O_DROP_DIR", Path.home() / ".rrz1o" / "localdrop")).expanduser()
FILES = BASE / "files"
META = BASE / "meta"
CONFIG = BASE / "config.json"

HOST = os.environ.get("RRZ1O_HOST", "0.0.0.0")
PORT = int(os.environ.get("RRZ1O_PORT", "8080"))
MAX_BYTES = 10 * 1024 * 1024 * 1024

FILES.mkdir(parents=True, exist_ok=True)
META.mkdir(parents=True, exist_ok=True)

if not CONFIG.exists():
    CONFIG.write_text(json.dumps({
        "brand": "RRZ1o",
        "version": "2.0.0",
        "max_file_size": "10GB"
    }, indent=2), encoding="utf-8")

TOKEN_FILE = BASE / "token"
if TOKEN_FILE.exists():
    TOKEN = TOKEN_FILE.read_text().strip()
else:
    TOKEN = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(TOKEN, encoding="utf-8")


def esc(value):
    return html.escape(str(value), quote=True)


def clean_name(name):
    name = os.path.basename(name).replace("\x00", "").strip()
    name = re.sub(r"[\r\n\t]+", "_", name)
    return name[:220] or "file"


def format_size(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size)
    for unit in units:
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024


def meta_path(fid):
    return META / f"{fid}.json"


def file_path(fid):
    return FILES / fid


def load_meta(fid):
    p = meta_path(fid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_meta(data):
    meta_path(data["id"]).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def all_files():
    result = []
    for p in META.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if file_path(data["id"]).exists():
                result.append(data)
        except Exception:
            pass
    return sorted(result, key=lambda x: x.get("created", 0), reverse=True)


def total_size():
    return sum(x.get("size", 0) for x in all_files())


def token_ok(handler):
    query = urllib.parse.parse_qs(
        urllib.parse.urlparse(handler.path).query
    )
    return (
        handler.headers.get("X-RRZ1O-Token") == TOKEN
        or query.get("token", [""])[0] == TOKEN
    )


def json_response(handler, data, status=200):
    raw = json.dumps(data, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(raw)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RRZ1o // LocalDrop</title>
<style>
*{box-sizing:border-box}
:root{
--bg:#06080d;
--panel:#0d1118;
--panel2:#111722;
--line:#202938;
--text:#f5f7fa;
--muted:#7f8a9b;
--accent:#fff;
--danger:#ff5668;
}
body{
margin:0;
background:
radial-gradient(circle at 50% -20%,#1b2330 0,#06080d 45%);
color:var(--text);
font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
min-height:100vh
}
a{color:inherit;text-decoration:none}
.container{max-width:1120px;margin:auto;padding:24px}
header{
display:flex;
justify-content:space-between;
align-items:center;
gap:20px;
padding:14px 0 28px
}
.brand{
font-weight:900;
font-size:25px;
letter-spacing:2px
}
.brand span{color:#8994a6}
.badge{
border:1px solid var(--line);
background:#0d121a;
padding:8px 12px;
border-radius:999px;
font-size:12px;
color:#aeb7c5
}
.hero{margin:28px 0 25px}
.hero h1{
font-size:clamp(34px,7vw,65px);
line-height:.98;
margin:0;
letter-spacing:-3px
}
.hero p{
color:var(--muted);
font-size:16px;
margin-top:16px
}
.grid{
display:grid;
grid-template-columns:2fr 1fr;
gap:18px
}
.card{
background:rgba(13,17,24,.88);
border:1px solid var(--line);
border-radius:22px;
padding:20px;
box-shadow:0 18px 70px rgba(0,0,0,.25)
}
.drop{
min-height:300px;
border:1px dashed #354153;
border-radius:18px;
display:flex;
align-items:center;
justify-content:center;
text-align:center;
padding:25px;
transition:.2s;
cursor:pointer
}
.drop.drag{
border-color:#fff;
background:#151b25;
transform:scale(1.01)
}
.drop-icon{
width:70px;
height:70px;
border-radius:20px;
background:#fff;
color:#05070b;
display:flex;
align-items:center;
justify-content:center;
font-size:30px;
font-weight:900;
margin:0 auto 18px
}
.drop h2{margin:0 0 8px}
.drop p{color:var(--muted);margin:0 0 20px}
.btn{
display:inline-flex;
align-items:center;
justify-content:center;
border:0;
border-radius:12px;
padding:12px 17px;
font-weight:800;
cursor:pointer;
background:#f5f7fa;
color:#07090d
}
.btn.secondary{
background:#1a202b;
color:#fff;
border:1px solid #293241
}
input[type=file]{display:none}
.stats{
display:grid;
grid-template-columns:repeat(3,1fr);
gap:10px;
margin-top:14px
}
.stat{
background:#0a0e15;
border:1px solid var(--line);
border-radius:15px;
padding:14px
}
.stat strong{font-size:20px;display:block}
.stat span{font-size:11px;color:var(--muted)}
.token{
margin-top:15px;
padding:13px;
background:#080b11;
border:1px solid var(--line);
border-radius:12px;
font-family:monospace;
font-size:12px;
word-break:break-all;
color:#b9c2cf
}
.toolbar{
display:flex;
gap:10px;
align-items:center;
justify-content:space-between;
margin-bottom:14px
}
.search{
width:100%;
background:#080c12;
border:1px solid var(--line);
border-radius:12px;
padding:12px 14px;
outline:none;
color:#fff
}
.files{margin-top:20px}
.file{
display:flex;
align-items:center;
justify-content:space-between;
gap:15px;
padding:16px 0;
border-bottom:1px solid var(--line)
}
.file:last-child{border-bottom:0}
.file-main{
display:flex;
align-items:center;
gap:13px;
min-width:0
}
.file-icon{
width:45px;
height:45px;
flex:none;
border-radius:13px;
background:#171d27;
display:flex;
align-items:center;
justify-content:center;
font-weight:900
}
.file-name{
font-weight:750;
overflow:hidden;
text-overflow:ellipsis;
white-space:nowrap;
max-width:430px
}
.file-meta{
font-size:12px;
color:var(--muted);
margin-top:4px
}
.actions{
display:flex;
gap:7px;
flex:none
}
.action{
border:1px solid var(--line);
background:#111722;
color:#fff;
padding:9px 11px;
border-radius:10px;
cursor:pointer;
font-size:12px;
font-weight:700
}
.action.delete{color:#ff7180}
.progress-wrap{
margin-top:15px;
display:none
}
.progress{
height:8px;
border-radius:20px;
background:#1a202b;
overflow:hidden
}
.progress-bar{
height:100%;
width:0%;
background:#fff;
transition:width .15s
}
.progress-text{
font-size:12px;
color:var(--muted);
margin-top:7px
}
.empty{
text-align:center;
padding:50px 15px;
color:var(--muted)
}
footer{
text-align:center;
padding:35px 10px 15px;
color:#687384;
font-size:12px
}
footer a{color:#cbd2dc}
.toast{
position:fixed;
right:20px;
bottom:20px;
background:#f5f7fa;
color:#080a0e;
padding:13px 17px;
border-radius:13px;
font-weight:750;
display:none;
z-index:20
}
@media(max-width:800px){
.container{padding:16px}
.grid{grid-template-columns:1fr}
.hero h1{letter-spacing:-2px}
.file{align-items:flex-start}
.actions{flex-direction:column}
.file-name{max-width:230px}
}
</style>
</head>
<body>
<div class="container">
<header>
<div class="brand">RRZ1o <span>// LOCALDROP</span></div>
<div class="badge">PRIVATE TRANSFER</div>
</header>

<section class="hero">
<h1>Drop. Share.<br>Done.</h1>
<p>Fast private file transfer for Termux & Linux.</p>
</section>

<div class="grid">
<div class="card">
<div class="drop" id="drop">
<div>
<div class="drop-icon">↑</div>
<h2>Drop files here</h2>
<p>or select files from your device</p>
<button class="btn" onclick="event.stopPropagation();fileInput.click()">SELECT FILES</button>
<input id="fileInput" type="file" multiple>
</div>
</div>

<div class="progress-wrap" id="progressWrap">
<div class="progress"><div class="progress-bar" id="progressBar"></div></div>
<div class="progress-text" id="progressText">Preparing upload...</div>
</div>

<div class="stats">
<div class="stat"><strong id="fileCount">0</strong><span>FILES</span></div>
<div class="stat"><strong id="totalSize">0 B</strong><span>STORAGE</span></div>
<div class="stat"><strong>10 GB</strong><span>MAX / FILE</span></div>
</div>
</div>

<div class="card">
<h3 style="margin-top:0">ACCESS TOKEN</h3>
<div class="token" id="token">TOKEN</div>
<button class="btn secondary" style="margin-top:10px;width:100%" onclick="copyToken()">COPY TOKEN</button>
</div>
</div>

<div class="card files">
<div class="toolbar">
<h3 style="margin:0">FILES</h3>
<input class="search" id="search" placeholder="Search files..." oninput="filterFiles()" style="max-width:300px">
</div>
<div id="list"></div>
</div>

<footer>
<div>RRZ1o // LOCALDROP</div>
<div style="margin-top:7px">
Telegram: <a href="https://t.me/RRZ1o" target="_blank">@RRZ1o</a>
&nbsp; • &nbsp;
Code by RRZ1o
&nbsp; • &nbsp;
<a href="https://github.com/RRZ1o" target="_blank">GitHub</a>
</div>
</footer>
</div>

<div class="toast" id="toast"></div>

<script>
const TOKEN=location.search.includes("token=")
?new URLSearchParams(location.search).get("token")
:null;

let files=[];

const fileInput=document.getElementById("fileInput");
const drop=document.getElementById("drop");
const list=document.getElementById("list");
const tokenBox=document.getElementById("token");
const toast=document.getElementById("toast");
const progressWrap=document.getElementById("progressWrap");
const progressBar=document.getElementById("progressBar");
const progressText=document.getElementById("progressText");

function showToast(t){
toast.textContent=t;
toast.style.display="block";
setTimeout(()=>toast.style.display="none",2200);
}

async function getToken(){
const r=await fetch("/api/token");
const j=await r.json();
tokenBox.textContent=j.token;
return j.token;
}

async function load(){
const r=await fetch("/api/files?token="+encodeURIComponent(tokenBox.textContent));
if(!r.ok)return;
files=await r.json();
render(files);
}

function formatSize(n){
const u=["B","KB","MB","GB","TB"];
let i=0;
while(n>=1024&&i<u.length-1){n/=1024;i++}
return n.toFixed(i?1:0)+" "+u[i];
}

function render(data){
document.getElementById("fileCount").textContent=data.length;
document.getElementById("totalSize").textContent=formatSize(
data.reduce((a,b)=>a+b.size,0)
);

if(!data.length){
list.innerHTML='<div class="empty">No files uploaded yet.</div>';
return;
}

list.innerHTML=data.map(f=>{
const icon=f.mime&&f.mime.startsWith("image/")?"IMG":
f.mime&&f.mime.startsWith("video/")?"VID":
f.mime&&f.mime.startsWith("audio/")?"AUD":"FILE";

return `
<div class="file" data-name="${escapeHtml(f.name).toLowerCase()}">
<div class="file-main">
<div class="file-icon">${icon}</div>
<div>
<div class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
<div class="file-meta">${formatSize(f.size)} · ${f.downloads||0} downloads · SHA256 ${f.sha256.slice(0,12)}</div>
</div>
</div>
<div class="actions">
<button class="action" onclick="downloadFile('${f.id}')">DOWNLOAD</button>
<button class="action" onclick="copyLink('${f.id}')">COPY</button>
<button class="action delete" onclick="deleteFile('${f.id}')">DELETE</button>
</div>
</div>`;
}).join("");
}

function escapeHtml(s){
return s.replace(/[&<>"']/g,m=>({
"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
}[m]));
}

function filterFiles(){
const q=document.getElementById("search").value.toLowerCase();
document.querySelectorAll(".file").forEach(x=>{
x.style.display=x.dataset.name.includes(q)?"flex":"none";
});
}

function downloadFile(id){
location.href="/d/"+id;
}

async function copyLink(id){
const url=location.origin+"/d/"+id+"?token="+encodeURIComponent(tokenBox.textContent);
await navigator.clipboard.writeText(url);
showToast("Download link copied");
}

async function copyToken(){
await navigator.clipboard.writeText(tokenBox.textContent);
showToast("Token copied");
}

async function deleteFile(id){
if(!confirm("Delete this file permanently?"))return;
const r=await fetch("/api/delete/"+id,{
method:"POST",
headers:{"X-RRZ1O-Token":tokenBox.textContent}
});
if(r.ok){
showToast("File deleted");
load();
}
}

function upload(file){
return new Promise((resolve,reject)=>{
if(file.size>10*1024*1024*1024){
showToast("Maximum file size is 10 GB");
reject();
return;
}

const xhr=new XMLHttpRequest();
const fd=new FormData();
fd.append("file",file);

xhr.open(
"POST",
"/api/upload?token="+encodeURIComponent(tokenBox.textContent)
);

xhr.upload.onprogress=e=>{
if(e.lengthComputable){
const p=(e.loaded/e.total)*100;
progressWrap.style.display="block";
progressBar.style.width=p+"%";
progressText.textContent=
"Uploading "+file.name+" — "+p.toFixed(0)+"%";
}
};

xhr.onload=()=>{
if(xhr.status>=200&&xhr.status<300){
progressBar.style.width="100%";
progressText.textContent="Upload complete";
resolve();
}else{
let j={};
try{j=JSON.parse(xhr.responseText)}catch(e){}
showToast(j.error||"Upload failed");
reject();
}
};

xhr.onerror=()=>{
showToast("Connection error");
reject();
};

xhr.send(fd);
});
}

async function uploadFiles(fs){
for(const file of fs){
try{
await upload(file);
}catch(e){}
}
setTimeout(()=>{
progressWrap.style.display="none";
progressBar.style.width="0%";
load();
},500);
}

fileInput.onchange=e=>uploadFiles([...e.target.files]);

drop.onclick=()=>{
fileInput.click();
};

drop.ondragover=e=>{
e.preventDefault();
drop.classList.add("drag");
};

drop.ondragleave=()=>{
drop.classList.remove("drag");
};

drop.ondrop=e=>{
e.preventDefault();
drop.classList.remove("drag");
uploadFiles([...e.dataTransfer.files]);
};

(async()=>{
const t=await getToken();
tokenBox.textContent=t;
load();
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def page(self):
        data = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self.page()

        if path == "/api/token":
            return json_response(self, {"token": TOKEN})

        if path == "/api/files":
            if not token_ok(self):
                return json_response(self, {"error": "unauthorized"}, 401)
            return json_response(self, all_files())

        if path.startswith("/d/"):
            fid = path[3:]
            meta = load_meta(fid)

            if not meta:
                return json_response(self, {"error": "not found"}, 404)

            fp = file_path(fid)

            if not fp.exists():
                return json_response(self, {"error": "not found"}, 404)

            name = clean_name(meta["name"])
            mime = meta.get("mime") or "application/octet-stream"
            size = fp.stat().st_size

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{name.replace(chr(34), "")}"'
            )
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            with fp.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

            meta["downloads"] = meta.get("downloads", 0) + 1
            save_meta(meta)
            return

        return json_response(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not token_ok(self):
            return json_response(self, {"error": "unauthorized"}, 401)

        if path.startswith("/api/delete/"):
            fid = path.rsplit("/", 1)[-1]
            meta = load_meta(fid)

            if not meta:
                return json_response(self, {"error": "not found"}, 404)

            try:
                file_path(fid).unlink(missing_ok=True)
                meta_path(fid).unlink(missing_ok=True)
            except Exception as e:
                return json_response(self, {"error": str(e)}, 500)

            return json_response(self, {"ok": True})

        if path == "/api/upload":
            return self.upload()

        return json_response(self, {"error": "not found"}, 404)

    def upload(self):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            return json_response(
                self,
                {"error": "multipart/form-data required"},
                400
            )

        match = re.search(r'boundary="?([^";]+)"?', content_type)

        if not match:
            return json_response(
                self,
                {"error": "invalid multipart boundary"},
                400
            )

        boundary = match.group(1).encode()
        content_length = int(
            self.headers.get("Content-Length", "0")
        )

        if content_length <= 0:
            return json_response(
                self,
                {"error": "empty upload"},
                400
            )

        if content_length > MAX_BYTES + 20 * 1024 * 1024:
            return json_response(
                self,
                {"error": "maximum file size is 10 GB"},
                413
            )

        body = self.rfile.read(content_length)
        marker = b"--" + boundary

        saved = []

        for part in body.split(marker):
            if b'filename=' not in part:
                continue

            if b"\r\n\r\n" not in part:
                continue

            headers, content = part.split(b"\r\n\r\n", 1)

            content = content.rstrip(b"\r\n-")

            header_text = headers.decode(
                "utf-8",
                "replace"
            )

            filename_match = re.search(
                r'filename="([^"]*)"',
                header_text
            )

            filename = (
                clean_name(filename_match.group(1))
                if filename_match
                else "upload"
            )

            if len(content) > MAX_BYTES:
                return json_response(
                    self,
                    {"error": "maximum file size is 10 GB"},
                    413
                )

            fid = secrets.token_hex(16)
            fp = file_path(fid)

            sha = hashlib.sha256()

            with fp.open("wb") as f:
                offset = 0

                while offset < len(content):
                    chunk = content[offset:offset + 1024 * 1024]
                    f.write(chunk)
                    sha.update(chunk)
                    offset += len(chunk)

            meta = {
                "id": fid,
                "name": filename,
                "size": len(content),
                "sha256": sha.hexdigest(),
                "mime": mimetypes.guess_type(filename)[0]
                or "application/octet-stream",
                "created": time.time(),
                "downloads": 0
            }

            save_meta(meta)
            saved.append(meta)

        return json_response(
            self,
            {
                "ok": True,
                "files": saved
            }
        )


def main():
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("          RRZ1o // LOCALDROP")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"  Local    : http://127.0.0.1:{PORT}")
    print(f"  Network  : http://YOUR-IP:{PORT}")
    print(f"  Max/File : 10 GB")
    print(f"  Telegram : @RRZ1o")
    print(f"  GitHub   : https://github.com/RRZ1o")
    print()
    print(f"  Token    : {TOKEN}")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    server = ThreadingHTTPServer((HOST, PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRRZ1o LocalDrop stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()