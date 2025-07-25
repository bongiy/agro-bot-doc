import os
from ftplib import FTP, error_perm

def get_ftp():
    """Отримує FTP-з'єднання з даними із змінних оточення."""
    ftp = FTP(os.getenv('FTP_HOST'))
    ftp.login(os.getenv('FTP_USER'), os.getenv('FTP_PASS'))
    return ftp

def ensure_dirs(ftp, remote_dir):
    """Рекурсивно створює підпапки на FTP, якщо їх ще немає."""
    if not remote_dir:
        return
    dirs = remote_dir.strip("/").split("/")
    path = ""
    for d in dirs:
        path = f"{path}/{d}" if path else d
        try:
            ftp.mkd(path)
        except error_perm as e:
            if not str(e).startswith('550'):  # "Directory already exists" (550)
                raise
    ftp.cwd("/")

def upload_file_ftp(local_file, remote_file):
    """
    Завантажує файл на FTP-сервер.
    local_file — шлях до локального файлу
    remote_file — шлях на FTP (наприклад, 'payers/Ivan_Ivanov_1/passport.pdf')
    """
    ftp = get_ftp()
    remote_dir = os.path.dirname(remote_file)
    ensure_dirs(ftp, remote_dir)
    # Переходимо у потрібну директорію
    if remote_dir:
        ftp.cwd(remote_dir)
    with open(local_file, 'rb') as f:
        ftp.storbinary(f'STOR {os.path.basename(remote_file)}', f)
    ftp.quit()

def download_file_ftp(remote_file, local_file):
    """
    Завантажує файл з FTP-сервера у локальний файл.
    remote_file — шлях на FTP
    local_file — шлях локального файлу
    """
    ftp = get_ftp()
    remote_dir = os.path.dirname(remote_file)
    if remote_dir:
        ftp.cwd(remote_dir)
    with open(local_file, 'wb') as f:
        ftp.retrbinary(f'RETR {os.path.basename(remote_file)}', f.write)
    ftp.quit()

def delete_file_ftp(remote_file):
    """
    Видаляє файл з FTP-сервера.
    remote_file — шлях на FTP
    """
    ftp = get_ftp()
    remote_dir = os.path.dirname(remote_file)
    if remote_dir:
        ftp.cwd(remote_dir)
    try:
        ftp.delete(os.path.basename(remote_file))
    except error_perm as e:
        if not str(e).startswith('550'):
            raise
    ftp.quit()
