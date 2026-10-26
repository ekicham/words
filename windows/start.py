"""Portable Windows web entry. No installation, registry writes or public listener."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App, serve


def open_browser(url):
    if sys.platform != 'win32':
        return webbrowser.open(url)
    # IE is commonly the default on Win7 and cannot run this application.
    import winreg
    for executable, suffix in [('chrome.exe', 'Google/Chrome/Application/chrome.exe'),
                               ('msedge.exe', 'Microsoft/Edge/Application/msedge.exe'),
                               ('firefox.exe', 'Mozilla Firefox/firefox.exe')]:
        candidates = []
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + executable, 0, winreg.KEY_READ | view) as key:
                        candidates.append(Path(winreg.QueryValue(key, None).strip('"')))
                except OSError: pass
        candidates += [Path(os.environ[name]) / suffix for name in ('LOCALAPPDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)') if os.environ.get(name)]
        for candidate in candidates:
            if candidate.is_file():
                try:
                    subprocess.Popen([str(candidate), url])
                    return True
                except OSError: pass
    print('未找到 Chrome / Edge / Firefox。请使用兼容 Win7 的浏览器打开：' + url, flush=True)
    print('请查看包内“使用说明.txt”；Windows 自带 IE 无法使用词屿。', flush=True)
    return False


def main():
    parser = argparse.ArgumentParser(description='词屿 Windows 便携版')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'WordIsleWeb'
    folder.mkdir(parents=True, exist_ok=True)
    url = 'http://127.0.0.1:%s/' % args.port
    # Hold one process per learning directory to protect in-progress assessments.
    with (folder / 'app.lock').open('a+b') as lock:
        lock.seek(0, 2)
        if not lock.tell(): lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print('词屿已经运行，请返回原启动窗口。', flush=True)
            if not args.no_browser: open_browser(url)
            return
        application = App(folder / 'words.sqlite3')
        try:
            server = serve(application, args.port)
        except OSError:
            raise SystemExit('端口 %s 已被其他程序使用，请关闭占用程序后重试。' % args.port)
        print('词屿 1.4.1 已启动：' + url + '\n学习记录：' + str(folder) + '\n请保留此窗口。退出时按 Ctrl+C 或关闭此窗口。', flush=True)
        try:
            if not args.no_browser: open_browser(url)
            server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            server.server_close()
            application.phonetics_lesson.local.close()


if __name__ == '__main__': main()
