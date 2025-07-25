import os
from ftplib import FTP, error_perm
from os import getenv
from io import BytesIO

def download_file_ftp_to_memory(remote_file):
    """
    Скачує файл з FTP у пам'ять (RAM), повертає BytesIO-об'єкт і ім'я файла.
    """
    from os import getenv
    from ftplib import FTP
    import os

    ftp = FTP(getenv('FTP_HOST'))
    ftp.login(getenv('FTP_USER'), getenv('FTP_PASS'))

    remote_dir = os.path.dirname(remote_file)
    filename = os.path.basename(remote_file)
    if remote_dir:
        ftp.cwd(remote_dir)

    bio = BytesIO()
    ftp.retrbinary(f'RETR {filename}', bio.write)
    ftp.quit()
    bio.seek(0)
    return bio, filename
    
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
    from os import getenv
    from ftplib import FTP, error_perm
    import os

    ftp = FTP(getenv('FTP_HOST'))
    ftp.login(getenv('FTP_USER'), getenv('FTP_PASS'))

    remote_dir = os.path.dirname(remote_file)
    if remote_dir:
        print("CWD to:", remote_dir)
        ftp.cwd(remote_dir)
        print("PWD:", ftp.pwd())
    print("Trying to download:", os.path.basename(remote_file), "to", local_file)
    with open(local_file, 'wb') as f:
        ftp.retrbinary(f'RETR {os.path.basename(remote_file)}', f.write)
    ftp.quit()
    print("Download finished, file size:", os.path.getsize(local_file))


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
