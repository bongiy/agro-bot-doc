from ftplib import FTP
import os

def upload_file_ftp(local_file, remote_file):
    from os import getenv
    ftp = FTP(getenv('FTP_HOST'))
    ftp.login(getenv('FTP_USER'), getenv('FTP_PASS'))
    # Створити підпапки, якщо треба (треба окремий код для рекурсивного створення, якщо структура складна)
    with open(local_file, 'rb') as f:
        ftp.storbinary(f'STOR {remote_file}', f)
    ftp.quit()

def download_file_ftp(remote_file, local_file):
    from os import getenv
    ftp = FTP(getenv('FTP_HOST'))
    ftp.login(getenv('FTP_USER'), getenv('FTP_PASS'))
    with open(local_file, 'wb') as f:
        ftp.retrbinary(f'RETR {remote_file}', f.write)
    ftp.quit()
