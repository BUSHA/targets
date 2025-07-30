import os
import requests
import re
import subprocess

def is_git_repo():
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def download_patch(url):
    pr_match = re.match(r'https://github.com/([^/]+)/([^/]+)/pull/(\d+)', url)
    commit_match = re.match(r'https://github.com/([^/]+)/([^/]+)/commit/([a-fA-F0-9]{7,40})', url)
    if pr_match:
        owner, repo, pr_number = pr_match.groups()
        patch_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}.patch"
        filename = f"pr_{pr_number}.patch"
    elif commit_match:
        owner, repo, sha = commit_match.groups()
        patch_url = f"https://github.com/{owner}/{repo}/commit/{sha}.patch"
        filename = f"commit_{sha[:8]}.patch"
    else:
        print("❌ Некоректне посилання на PR або коміт.")
        return None

    print(f"📥 Завантаження: {patch_url}")
    try:
        response = requests.get(patch_url)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"✅ Збережено як: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Помилка при завантаженні: {e}")
        return None

def apply_patch(filename):
    if not is_git_repo():
        print("❌ Поточна директорія не є Git-репозиторієм.")
        return False

    print(f"🛠 Спроба застосувати патч: {filename}")
    try:
        subprocess.run(["git", "apply", filename], check=True)
        print(f"✅ Патч застосовано: {filename}")
        os.remove(filename)
        print(f"🧹 Видалено файл патчу: {filename}")
        return True
    except subprocess.CalledProcessError:
        print("⚠️ Не вдалося застосувати патч звичайним способом. Пробую --reject --whitespace=fix...")
        try:
            subprocess.run(["git", "apply", "--reject", "--whitespace=fix", filename], check=True)
            print(f"⚠️ Патч застосовано частково або з відхиленнями.")
            return False
        except subprocess.CalledProcessError:
            print(f"❌ Повністю не вдалося застосувати патч.")
            return False

if __name__ == "__main__":
    print("\033[96m")  # Бірюзовий
    print("+" + "-"*66 + "+")
    print("|{:^66}|".format("Скрипт для швидкого скачування і застосування patch-файлу з GitHub"))
    print("+" + "-"*66 + "+")
    print("\033[0m")
    print()

    url = input("Встав посилання на PR або коміт GitHub: ").strip()
    patch_file = download_patch(url)
    if patch_file:
        answer = input("Застосувати патч одразу? [y/n]: ").strip().lower()
        if answer == "y":
            success = apply_patch(patch_file)
            if not success:
                clean = input("Патч не застосовано повністю. Видалити патч-файл? [y/n]: ").strip().lower()
                if clean == "y":
                    try:
                        os.remove(patch_file)
                        print(f"🧹 Видалено файл патчу: {patch_file}")
                    except Exception as e:
                        print(f"❌ Не вдалося видалити файл: {e}")
                else:
                    print(f"Файл патчу залишено: {patch_file}")
        else:
            print(f"Патч просто збережено як: {patch_file}")
