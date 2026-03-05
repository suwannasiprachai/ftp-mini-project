# Flask สร้างเว็บเซิร์ฟเวอร์ ,request รับค่าจากฟอร์ม ,session เก็บข้อมูลผู้ใช้หลัง login ,send_file ส่งไฟล์ให้ดาวน์โหลด
# secure_filename ป้องกันชื่อไฟล์อันตราย ,FTP ใช้เชื่อมต่อ FTP ,os จัดการไฟล์/โฟลเดอร์
# เป็นการ เรียกใช้ library ที่จำเป็นในระบบ
from flask import Flask, request, render_template, redirect, session, send_file
from werkzeug.utils import secure_filename
from ftplib import FTP
import os

# สร้าง Flask Application และกำหนด secret_key ใช้สำหรับ เข้ารหัส session ป้องกันการปลอม session ระบบนี้ใช้ session 
# เพื่อเก็บ username password หลังจาก login สำเร็จ
app = Flask(__name__)
app.secret_key = "secret123" # secret_key ใช้เข้ารหัส session ,session จะเก็บ username/password ไว้ชั่วคราว

# ==============================
# FTP CONFIG(คอนฟิค) (สำคัญมาก)
# ==============================
# กำหนดข้อมูล FTP Server FTP_HOST = "ftp" คือชื่อ service ใน docker-compose Container web จะเชื่อมต่อ FTP ผ่าน ftp:21
FTP_HOST = "ftp"   # ชื่อ service ใน docker-compose
FTP_PORT = 21

# ใช้สำหรับ เก็บไฟล์ชั่วคราวตอนดาวน์โหลด 
# ตอนดาวน์โหลดคือ: FTP → โหลดมาไว้ temp(เท้ม) → ส่งให้ browser → ไฟล์ยังอยู่ใน temp
TEMP_FOLDER = "temp" # FTP → โหลดมา temp → ส่งให้ browser(เบราวเซอร์)
os.makedirs(TEMP_FOLDER, exist_ok=True)


# ==============================
# ฟังก์ชันเชื่อมต่อ FTP
# ==============================
# ตรวจสอบว่ามี session user หรือไม่ ถ้ามี → เชื่อมต่อ FTP login ด้วย user ที่เก็บไว้ใน session เปิด passive mode return object ftp
# สร้างการเชื่อมต่อ FTP สำหรับ route ต่าง ๆ ขั้นตอน ตรวจสอบ session if "user" not in session ถ้ายังไม่ login → กลับหน้า login
def ftp_connect():
    if "user" not in session:
        return None

    ftp = FTP()
    ftp.connect(FTP_HOST, FTP_PORT) # เชื่อมต่อ FTP
    ftp.login(session["user"], session["pass"]) # login เข้า FTP
    ftp.set_pasv(True) # เปิด Passive Mode ใช้สำหรับ Docker network
    return ftp


# ==============================
# LOGIN
# ==============================
# GET แสดงหน้า login.html ตอนกด Login Browser → Flask → พยายาม login เข้า FTP
@app.route("/", methods=["GET", "POST"]) # ตรวจสอบผู้ใช้ผ่าน FTP , FTP server ทำหน้าที่เหมือน เซิร์ฟเวอร์ตรวจสอบสิทธิ์
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        try:
            ftp = FTP()
            ftp.connect(FTP_HOST, FTP_PORT)

# ถ้า login FTP สำเร็จ: เก็บ user/pass ใน session redirect ไป /dashboard 
# ถ้าไม่สำเร็จ: แสดง "Login Failed" เว็บนี้ใช้ FTP เป็นตัวตรวจสอบรหัสผ่าน
            ftp.login(username, password) 
            ftp.quit()

            session["user"] = username
            session["pass"] = password
            return redirect("/dashboard")

        except:
            return "Login Failed"

    return render_template("login.html")


# ==============================
# DASHBOARD (ดึงไฟล์จาก FTP)
# ==============================
@app.route("/dashboard") # การทำงาน เชื่อมต่อ FTP ดึงรายการไฟล์ files = ftp.nlst() ส่งรายชื่อไฟล์ไป dashboard.html
# Browser → Flask → FTP.nlst() → ได้รายชื่อไฟล์ → ส่งไป HTML
def dashboard():
    ftp = ftp_connect()
    if not ftp:
        return redirect("/")

    files = ftp.nlst()
    ftp.quit()

    return render_template("dashboard.html",
                           user=session["user"],
                           files=files)


# ==============================
# UPLOAD (ผ่าน FTP เท่านั้น)
# ==============================
@app.route("/upload", methods=["POST"]) # รับไฟล์จาก form ทำชื่อไฟล์ให้ปลอดภัย
def upload():
    ftp = ftp_connect()
    if not ftp:
        return redirect("/")

    file = request.files.get("file")
    if not file or file.filename == "":
        return redirect("/dashboard")

    filename = secure_filename(file.filename) # อัปโหลดไป FTP

    ftp.storbinary(f"STOR {filename}", file.stream)
    ftp.quit()

    return redirect("/dashboard")


# ==============================
# DOWNLOAD (ผ่าน FTP เท่านั้น)
# ==============================
@app.route("/download/<filename>") # เชื่อม FTP โหลดไฟล์จาก FTP
def download(filename):
    ftp = ftp_connect()
    if not ftp:
        return redirect("/")

    filename = secure_filename(filename)
    local_path = os.path.join(TEMP_FOLDER, filename)

    with open(local_path, "wb") as f:
        ftp.retrbinary(f"RETR {filename}", f.write) # บันทึกไว้ใน temp ส่งไฟล์กลับ browser

    ftp.quit()

    return send_file(local_path, as_attachment=True)


# ==============================
# DELETE (ผ่าน FTP เท่านั้น)
# ==============================
@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename): 
    ftp = ftp_connect()
    if not ftp:
        return redirect("/")

    filename = secure_filename(filename)
    ftp.delete(filename) # Browser กดลบ → Flask → FTP.delete() → ลบไฟล์ใน server_files จริง
    ftp.quit()

    return redirect("/dashboard") # ใช้คำสั่ง FTP ftp.nlst() เพื่อดึงรายการไฟล์จาก FTP Server


# ==============================
# LOGOUT
# ==============================
@app.route("/logout") 
def logout():
    session.clear() # ลบ session ทิ้ง → ต้อง login ใหม่
    return redirect("/")


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

# วิธีรัน docker-compose up --build หรือ docker compose up --build
# และเข้าไปที่ http://localhost:8000

# FTP อยู่ใน container: ftp-server ใช้ image: stilliard/pure-ftpd ไฟล์จริงเก็บที่ ./server_files ในเครื่อง Host