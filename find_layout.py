# Для роботи цього скрипту потрібні зовнішні бібліотеки.
# Встановіть їх командами:
# pip install simple-term-menu
# pip install pyperclip

import json
import os
import sys
import pathlib
import difflib
from collections import defaultdict

# Спроба імпортувати необхідні бібліотеки
try:
    from simple_term_menu import TerminalMenu
except ImportError:
    print("Помилка: бібліотеку 'simple-term-menu' не знайдено.")
    print("Будь ласка, встановіть її командою: pip install simple-term-menu")
    sys.exit(1)

try:
    import pyperclip
except ImportError:
    print("Помилка: бібліотеку 'pyperclip' не знайдено.")
    print("Будь ласка, встановіть її командою: pip install pyperclip")
    sys.exit(1)


# --- Налаштування ---
MATCH_THRESHOLD = 80.0
SEARCH_DIRS = ['RX', 'TX']
TARGETS_FILENAME = 'targets.json'
# --------------------

# Клас для кольорового виводу в терміналі
class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    CYAN = '\033[96m'
    OKGREEN = '\033[92m'
    YELLOW = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def wait_for_enter(prompt_text):
    """
    Виводить повідомлення і надійно очікує натискання клавіші Enter,
    працюючи коректно навіть у "сирому" (raw) режимі термінала.
    """
    print(f"{BColors.BOLD}{prompt_text}{BColors.ENDC}", end="", flush=True)
    
    if os.name == 'nt':  # Для Windows
        import msvcrt
        while True:
            if msvcrt.getch() in (b'\r', b'\n'):
                break
    else:  # Для Linux, macOS (POSIX)
        import tty
        import termios
        if not sys.stdin.isatty():
            input()
            return
            
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                char = sys.stdin.read(1)
                if char in ('\r', '\n'):
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print()

def get_json_from_clipboard():
    """Отримує JSON з системного буфера обміну."""
    print("Спроба отримати JSON з буфера обміну...")
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content or not clipboard_content.strip():
            raise ValueError("Буфер обміну порожній або містить лише пробіли.")
        
        user_data = json.loads(clipboard_content)
        print(f"{BColors.OKGREEN}✓ JSON успішно отримано та розпарсено з буфера обміну.{BColors.ENDC}")
        return user_data
    except pyperclip.PyperclipException:
        raise SystemExit(f"{BColors.FAIL}Помилка доступу до буфера обміну.\n"
                         f"Переконайтесь, що у вас встановлені утиліти xclip/xsel (Linux) або pbcopy/pbpaste (macOS).{BColors.ENDC}")
    except json.JSONDecodeError:
        raise ValueError("Вміст буфера обміну не є коректним JSON.")
    except ValueError as e:
        raise e

def build_layout_map(targets_data):
    layout_to_devices = defaultdict(list)
    def traverse(node):
        if isinstance(node, dict):
            if 'layout_file' in node and 'product_name' in node:
                layout_to_devices[node['layout_file']].append(node['product_name'])
            for value in node.values():
                traverse(value)
        elif isinstance(node, list):
            for item in node:
                traverse(item)
    traverse(targets_data)
    return dict(layout_to_devices)

def calculate_match_percentage(base_data, compare_data):
    if not isinstance(base_data, dict) or not isinstance(compare_data, dict): return 0.0
    total_keys = len(base_data)
    if total_keys == 0: return 100.0 if not compare_data else 0.0
    match_count = 0
    for key, value in base_data.items():
        if key in compare_data and compare_data[key] == value:
            match_count += 1
    return (match_count / total_keys) * 100

def find_matching_files(user_data, layout_map):
    script_dir = pathlib.Path(__file__).parent
    found_matches = []
    print(f"\nРозпочинаю пошук у папках: {', '.join(SEARCH_DIRS)}...")
    for subdir in SEARCH_DIRS:
        search_path = script_dir / subdir
        if not search_path.is_dir(): continue
        for file_path in search_path.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                percentage = calculate_match_percentage(user_data, file_data)
                if percentage >= MATCH_THRESHOLD:
                    devices = layout_map.get(file_path.name, [])
                    found_matches.append((file_path, percentage, devices, file_data))
            except (json.JSONDecodeError, IOError):
                continue
    return found_matches

# --- ЗМІНЕНО: Повертаємось до стандартного компактного diff ---
def display_classic_diff(user_data, file_data, file_path_str):
    """Форматує та виводить diff у стандартному стилі unified_diff."""
    user_json_str = json.dumps(user_data, indent=4, sort_keys=True).splitlines()
    file_json_str = json.dumps(file_data, indent=4, sort_keys=True).splitlines()

    # Ми більше не вказуємо параметр 'n' (кількість рядків контексту),
    # щоб difflib використовував стандартне значення (зазвичай 3).
    diff = difflib.unified_diff(
        user_json_str,
        file_json_str,
        fromfile='Ваш_ввід_з_буфера',
        tofile=file_path_str,
        lineterm=''
    )

    print("\n" + "="*80)
    print(f"{BColors.BOLD}Порівняння для файлу: {file_path_str}{BColors.ENDC}")
    print("="*80)
    
    has_diff = False
    for line in diff:
        has_diff = True
        if line.startswith('+++'): print(f"{BColors.OKGREEN}{line}{BColors.ENDC}")
        elif line.startswith('---'): print(f"{BColors.FAIL}{line}{BColors.ENDC}")
        elif line.startswith('+'): print(f"{BColors.OKGREEN}{line}{BColors.ENDC}")
        elif line.startswith('-'): print(f"{BColors.FAIL}{line}{BColors.ENDC}")
        elif line.startswith('@@'): print(f"{BColors.CYAN}{line}{BColors.ENDC}")
        else: print(line)
    
    if not has_diff:
        print(f"{BColors.OKGREEN}Файли повністю ідентичні (після сортування ключів).{BColors.ENDC}")

    print("="*80 + "\n")

def format_device_list_string(devices):
    if not devices:
        return ""
    count = len(devices)
    if count <= 2:
        return f"Використовується в: {', '.join(devices)}"
    else:
        remaining = count - 2
        last_digit = remaining % 10
        last_two_digits = remaining % 100
        if last_two_digits in {11, 12, 13, 14}: unit = "пристроїв"
        elif last_digit == 1: unit = "пристрій"
        elif last_digit in {2, 3, 4}: unit = "пристрої"
        else: unit = "пристроїв"
        return f"Використовується в: {devices[0]}, {devices[1]} і ще {remaining} {unit}"


def main():
    """Головна функція скрипту."""
    script_dir = pathlib.Path(__file__).parent
    targets_path = script_dir / TARGETS_FILENAME
    layout_map = {}
    try:
        with open(targets_path, 'r', encoding='utf-8') as f:
            targets_data = json.load(f)
        layout_map = build_layout_map(targets_data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    wait_for_enter("Будь ласка, скопіюйте JSON леяут і натисніть Enter для початку пошуку...")

    try:
        user_data = get_json_from_clipboard()
    except (ValueError, SystemExit) as e:
        print(f"\n{BColors.FAIL}Помилка: {e}{BColors.ENDC}")
        sys.exit(1)

    matches = find_matching_files(user_data, layout_map)
    
    if not matches:
        print(f"\n{BColors.BOLD}Результат: Співпадінь з порогом >= {MATCH_THRESHOLD}% не знайдено.{BColors.ENDC}")
        return

    matches.sort(key=lambda item: item[1], reverse=True)
    
    while True:
        menu_entries = []
        for path, percentage, devices, _ in matches:
            relative_path = os.path.join(path.parent.name, path.name)
            percent_str = f"{percentage:6.2f}%"
            entry = f"[{percent_str}] {relative_path}"
            if devices:
                device_str = format_device_list_string(devices)
                entry += f"  ({device_str})"
            menu_entries.append(entry)

        terminal_menu = TerminalMenu(
            menu_entries,
            title="Оберіть файл для перегляду diff (використовуйте стрілки, Enter для вибору, 'q' або Esc для виходу):",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_yellow", "fg_black"),
            cycle_cursor=True,
            clear_screen=True,
        )
        
        selected_index = terminal_menu.show()
        
        if selected_index is None:
            break
        
        chosen_match = matches[selected_index]
        path, _, _, file_data = chosen_match
        relative_path = os.path.join(path.parent.name, path.name)
        
        display_classic_diff(user_data, file_data, relative_path)
        
        wait_for_enter("Натисніть Enter, щоб повернутись до меню...")

    print("\nРоботу завершено.")


if __name__ == "__main__":
    main()