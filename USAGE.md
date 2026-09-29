Usage

Clone

git clone https://github.com/RRZ1o/LocalDrop.git
cd LocalDrop

Run

Linux

python3 localdrop.py

Termux

python localdrop.py

Open LocalDrop

After starting the server, open:

http://127.0.0.1:8080

For other devices on the same local network:

http://YOUR-IP:8080

Example:

http://192.168.1.10:8080

Upload Files

1. Open LocalDrop in your browser.
2. Click SELECT FILES.
3. Select one or multiple files.
4. You can also drag and drop files into the upload area.
5. Wait until the upload is complete.

Maximum file size:

10 GB

Download

Click DOWNLOAD next to any uploaded file.

Copy Download Link

Click COPY to copy the download link.

Delete

Click DELETE to permanently remove a file.

Search

Use the search box to quickly find uploaded files.

Stop Server

Press:

CTRL + C

Change Port

Run LocalDrop on another port:

RRZ1O_PORT=9090 python3 localdrop.py

Then open:

http://127.0.0.1:9090

Change Storage Directory

You can change where uploaded files are stored:

RRZ1O_DROP_DIR="$HOME/MyFiles" python3 localdrop.py



Author

RRZ1o

Telegram: @RRZ1o

GitHub: https://github.com/RRZ1o