import os
from ftplib import FTP, error_perm

def get_ftp():
    """Повертає з'єднання з FTP-сервером з ENV."""
    ftp = FTP(os.getenv('FTP_HOST'))
    ftp.login(os.getenv('FTP_USER'), os.getenv('FTP_PASS'))
    return ftp

def ensure_dirs(ftp, remote_dir):
    """Рекурсивно створює вкладені підпапки на FTP, якщо їх ще немає, і входить у них по черзі."""
    if not remote_dir or remote_dir in (".", "/"):
        return
    dirs = remote_dir.strip("/").split("/")
    for d in dirs:
        try:
            ftp.mkd(d)
        except error_perm as e:
            if not str(e).startswith('550'):
                raise
        ftp.cwd(d)  # обов'язково заходити в кожну папку по черзі!
    # Після створення і переходу залишаємося у фінальній теці

def upload_file_ftp(local_file, remote_file):
    from os import getenv
    ftp = FTP(getenv('FTP_HOST'))
    ftp.login(getenv('FTP_USER'), getenv('FTP_PASS'))
    remote_dir = os.path.dirname(remote_file)
    current_dir = ftp.pwd()
    if remote_dir:
        ensure_dirs(ftp, remote_dir)
    with open(local_file, 'rb') as f:
        ftp.storbinary(f'STOR ' + os.path.basename(remote_file), f)
    ftp.cwd(current_dir)  # повертаємося назад у корінь
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
