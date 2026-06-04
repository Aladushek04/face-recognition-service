"""Beginner-friendly terminal UI for StashDB scraper, cleanup, and indexing."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


COLORS = {
    "reset": "\033[0m",
    "dim": "\033[90m",
    "cyan": "\033[96m",
    "magenta": "\033[95m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
}


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input(f"\n{COLORS['dim']}Нажми Enter, чтобы вернуться в меню...{COLORS['reset']}")


def read_key() -> str:
    if os.name == "nt":
        import msvcrt

        try:
            key = msvcrt.getwch()
        except KeyboardInterrupt:
            return "quit"
        if key in ("\x00", "\xe0"):
            arrow = msvcrt.getwch()
            return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(arrow, "")
        if key == "\r":
            return "enter"
        if key == "\x03":
            return "quit"
        return key.lower()

    try:
        key = sys.stdin.read(1).lower()
    except KeyboardInterrupt:
        return "quit"
    return "enter" if key in ("\n", "\r") else key


def menu(title: str, items: list[tuple[str, str]]) -> int | None:
    index = 0
    while True:
        clear()
        print(f"{COLORS['magenta']}> {title}{COLORS['reset']}\n")
        for i, (label, description) in enumerate(items):
            prefix = f"{COLORS['cyan']}> " if i == index else "  "
            color = COLORS["cyan"] if i == index else ""
            suffix = COLORS["reset"] if i == index else ""
            print(f"{prefix}{color}{label}{suffix} {COLORS['dim']}- {description}{COLORS['reset']}")
        print(f"\n{COLORS['dim']}Стрелки или j/k - выбор, Enter - открыть, q/й или Ctrl+C - выйти{COLORS['reset']}")

        key = read_key()
        if key in ("q", "й", "quit", "\x1b"):
            return None
        if key.isdigit():
            number = int(key)
            if 1 <= number <= len(items):
                return number - 1
        if key in ("up", "k"):
            index = (index - 1) % len(items)
        elif key in ("down", "j"):
            index = (index + 1) % len(items)
        elif key == "enter":
            return index


def section(title: str, hint: str | None = None) -> None:
    print(f"\n{COLORS['cyan']}{title}{COLORS['reset']}")
    if hint:
        print(f"{COLORS['dim']}{hint}{COLORS['reset']}")


def ask_text(label: str, default: str | None = None, *, hint: str | None = None) -> str | None:
    if hint:
        print(f"{COLORS['dim']}{hint}{COLORS['reset']}")
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{label}{suffix}: ").strip()
    if not value:
        return default
    return value


def ask_int(label: str, default: int | None = None, *, hint: str | None = None) -> int | None:
    while True:
        raw = ask_text(label, str(default) if default is not None else None, hint=hint)
        if raw in (None, ""):
            return default
        try:
            return int(raw)
        except ValueError:
            print(f"{COLORS['yellow']}Введи число или оставь поле пустым.{COLORS['reset']}")


def ask_float(label: str, default: float, *, hint: str | None = None) -> float:
    while True:
        raw = ask_text(label, str(default), hint=hint)
        if raw in (None, ""):
            return default
        try:
            return float(raw)
        except ValueError:
            print(f"{COLORS['yellow']}Введи число, например 0.5.{COLORS['reset']}")


def ask_yes_no(label: str, default: bool = False, *, yes: str | None = None, no: str | None = None) -> bool:
    default_text = "Y/n" if default else "y/N"
    if yes or no:
        print(f"{COLORS['dim']}Y = {yes or 'да'}; N = {no or 'нет'}{COLORS['reset']}")
    while True:
        raw = input(f"{label} [{default_text}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "д", "да"}:
            return True
        if raw in {"n", "no", "н", "нет"}:
            return False
        print(f"{COLORS['yellow']}Ответь Y или N.{COLORS['reset']}")


def select_value(
    label: str,
    values: list[tuple[str, str | None, str]],
    default_index: int = 0,
) -> tuple[str | None, str]:
    print(label)
    for i, (display, _value, description) in enumerate(values, start=1):
        marker = " *" if i - 1 == default_index else ""
        print(f"  {i}. {display}{marker} {COLORS['dim']}- {description}{COLORS['reset']}")
    while True:
        raw = input("Номер варианта: ").strip()
        if not raw:
            value = values[default_index]
            return value[1], value[0]
        try:
            idx = int(raw) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(values):
            value = values[idx]
            return value[1], value[0]
        print(f"{COLORS['yellow']}Выбери номер из списка.{COLORS['reset']}")


def add_arg(args: list[str], summary: list[str], flag: str, value: str | int | float | None, text: str) -> None:
    if value is None or value == "":
        return
    args += [flag, str(value)]
    summary.append(text)


def country_filters() -> tuple[list[str], list[str]]:
    args: list[str] = []
    summary: list[str] = []

    section("Country filter")
    if ask_yes_no(
        "Use preferred country map?",
        True,
        yes="keep green countries from the map; skip red Asia/Africa/Middle East countries and empty country profiles",
        no="do not filter by country",
    ):
        args += ["--country-region", "preferred-map"]
        summary.append("Countries: preferred green map")
        if ask_yes_no(
            "Keep profiles with empty country?",
            False,
            yes="unknown country will pass the country filter",
            no="unknown country will be skipped",
        ):
            args.append("--allow-unknown-country")
            summary.append("Countries: empty/unknown allowed")
        else:
            summary.append("Countries: empty/unknown skipped")

        extra_include = ask_text(
            "Extra countries to include, comma-separated",
            None,
            hint="Optional. Example: Australia,New Zealand",
        )
        add_arg(args, summary, "--include-countries", extra_include, f"Extra include countries: {extra_include}")
        extra_exclude = ask_text(
            "Extra countries to exclude, comma-separated",
            None,
            hint="Optional. Example: Turkey,Georgia",
        )
        add_arg(args, summary, "--exclude-countries", extra_exclude, f"Extra exclude countries: {extra_exclude}")
    else:
        summary.append("Countries: no country filter")

    return args, summary


def common_filters(*, cleanup_mode: bool = False) -> tuple[list[str], list[str]]:
    args: list[str] = []
    summary: list[str] = []

    section("1. Основные фильтры")
    gender, gender_label = select_value(
        "Кого оставить по полу?",
        [
            ("Female", "female", "обычный выбор для актрис"),
            ("Male", "male", "актеры"),
            ("Any", None, "не фильтровать по полу"),
        ],
        default_index=0,
    )
    breast_type, breast_label = select_value(
        "\nBreast type",
        [
            ("Augmented / Fake", "augmented", "только augmented; Natural и пустые значения отсекаются"),
            ("Natural", "natural", "только Natural"),
            ("NA", "na", "только NA"),
            ("Any", None, "не фильтровать по breast type"),
        ],
        default_index=0,
    )
    if gender:
        args += ["--gender", gender]
    summary.append(f"Пол: {gender_label}")
    if breast_type:
        args += ["--breast-type", breast_type]
    summary.append(f"Breast type: {breast_label}")

    section("2. Качество профиля")
    min_scenes = ask_int(
        "Минимум сцен",
        10,
        hint="Например 10: профили с 0-9 сценами будут отсеяны.",
    )
    min_birth_year = ask_int(
        "Минимальный год рождения",
        1960,
        hint="Например 1960: слишком старые профили будут отсеяны. Пусто = не фильтровать.",
    )
    max_birth_year = ask_int("Максимальный год рождения", None, hint="Обычно можно оставить пустым.")
    add_arg(args, summary, "--min-scenes", min_scenes, f"Сцен: минимум {min_scenes}")
    add_arg(args, summary, "--min-birth-year", min_birth_year, f"Год рождения: от {min_birth_year}")
    add_arg(args, summary, "--max-birth-year", max_birth_year, f"Год рождения: до {max_birth_year}")

    section("3. Необязательные фильтры по датам", "Если оставить пустым, этот фильтр не применяется.")
    exact_birthdate = ask_text("Точная дата рождения YYYY-MM-DD", None)
    birthdate_from = ask_text("Дата рождения от YYYY-MM-DD", None)
    birthdate_to = ask_text("Дата рождения до YYYY-MM-DD", None)
    active_from = ask_int("Career active от года", None)
    active_to = ask_int("Career active до года", None)
    add_arg(args, summary, "--birthdate", exact_birthdate, f"Точная дата рождения: {exact_birthdate}")
    add_arg(args, summary, "--birthdate-from", birthdate_from, f"Дата рождения: от {birthdate_from}")
    add_arg(args, summary, "--birthdate-to", birthdate_to, f"Дата рождения: до {birthdate_to}")
    add_arg(args, summary, "--active-from", active_from, f"Career active: от {active_from}")
    add_arg(args, summary, "--active-to", active_to, f"Career active: до {active_to}")

    section("4. Фото профиля")
    if cleanup_mode:
        require_image = ask_yes_no(
            "Удалять тех, у кого нет фото профиля?",
            True,
            yes="без фото попадут в список удаления",
            no="наличие фото не будет проверяться",
        )
    else:
        require_image = ask_yes_no(
            "Импортировать только профили с фото?",
            True,
            yes="профили без фото будут пропущены",
            no="профили без фото тоже могут попасть в БД",
        )
    if require_image:
        args.append("--require-image")
        summary.append("Фото профиля: обязательно")
    else:
        summary.append("Фото профиля: не проверяется")

    return args, summary


def print_summary(summary: list[str], command: list[str], *, danger: bool = False) -> None:
    print(f"\n{COLORS['green']}Итог выбранных настроек:{COLORS['reset']}")
    for item in summary:
        print(f"  - {item}")
    print(f"\n{COLORS['yellow']}Команда, которая будет выполнена:{COLORS['reset']}")
    print(subprocess.list2cmdline(command))
    if danger:
        print(f"\n{COLORS['red']}Внимание: этот запуск будет удалять строки из БД и папки актеров.{COLORS['reset']}")


def run_command(command: list[str], summary: list[str], *, danger: bool = False) -> None:
    print_summary(summary, command, danger=danger)
    if not ask_yes_no("Запустить сейчас?", True, yes="выполнить команду", no="вернуться без запуска"):
        return
    print()
    try:
        subprocess.run(command, cwd=ROOT, check=False)
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Команда остановлена пользователем.{COLORS['reset']}")


def scrape_flow(*, backfill: bool = False) -> None:
    clear()
    title = "Обновить метаданные существующих" if backfill else "Скраппинг StashDB"
    print(f"{COLORS['magenta']}> {title}{COLORS['reset']}")
    command = [PYTHON, str(ROOT / "scripts" / "scrape_stashdb.py")]
    filter_args, summary = common_filters()
    command += filter_args
    country_args, country_summary = country_filters()
    command += country_args
    summary += country_summary

    section("5. Режим запуска")
    if backfill:
        command += ["--all", "--no-images", "--update-existing"]
        summary += [
            "Режим: обновить существующие записи",
            "Картинки: не скачивать",
            "Объем: все страницы, которые вернет StashDB",
        ]
    else:
        if ask_yes_no(
            "Скрапить все подходящие страницы?",
            True,
            yes="идти по всем страницам StashDB",
            no="задать лимит новых анкет",
        ):
            command.append("--all")
            summary.append("Объем: все подходящие страницы")
        else:
            limit = ask_int("Лимит новых анкет", 1000)
            add_arg(command, summary, "--limit", limit, f"Лимит новых анкет: {limit}")
        if ask_yes_no(
            "Не скачивать фото сейчас?",
            False,
            yes="только метаданные, без файлов фото",
            no="скачивать фото профиля",
        ):
            command.append("--no-images")
            summary.append("Картинки: не скачивать")
        else:
            summary.append("Картинки: скачивать")
            section("6. Настройки скачивания фото", "Для распознавания лучше 3-5 фото, где лицо хорошо видно.")
            image_count = ask_int(
                "Сколько фото скачивать на актрису",
                3,
                hint="0 = скачать все доступные фото; 3-5 обычно достаточно для face index.",
            )
            image_order, image_order_label = select_value(
                "Какие фото брать первыми?",
                [
                    ("Largest", "largest", "самые большие по разрешению"),
                    ("From end", "last", "с конца списка StashDB; часто это более новые/другие фото"),
                    ("From start", "first", "с начала списка StashDB"),
                ],
                default_index=1,
            )
            validate_faces = ask_yes_no(
                "Проверять, что на фото видно лицо?",
                True,
                yes="скачанное фото без найденного лица будет удалено",
                no="сохранять все выбранные фото",
            )
            add_arg(command, summary, "--image-count", image_count, f"Фото на актрису: {'все' if image_count == 0 else image_count}")
            add_arg(command, summary, "--image-order", image_order, f"Порядок фото: {image_order_label}")
            if validate_faces:
                command.append("--validate-image-faces")
                summary.append("Проверка лица на фото: включена")
            else:
                summary.append("Проверка лица на фото: выключена")
        if ask_yes_no(
            "Обновлять уже существующих актеров?",
            False,
            yes="перезаписать StashDB-метаданные существующих строк",
            no="существующие строки пропускать",
        ):
            command.append("--update-existing")
            summary.append("Существующие записи: обновлять")
        else:
            summary.append("Существующие записи: пропускать")

    section("7. Технические настройки", "Обычно можно просто нажимать Enter.")
    page_size = ask_int("Размер страницы StashDB", 100)
    delay = ask_float("Пауза между обработкой анкет, сек", 0.5)
    resume_page = ask_int("Продолжить со страницы", None, hint="Пусто = начать с 1 страницы.")
    retries = ask_int("Повторы при ошибке сети", 8)
    retry_delay = ask_float("Начальная пауза перед повтором, сек", 10.0)
    dry_run = ask_yes_no(
        "Тестовый запуск без записи в БД?",
        False,
        yes="ничего не записывать, только показать процесс",
        no="записывать изменения",
    )
    if dry_run:
        command.append("--dry-run")
        summary.append("Тестовый запуск: да, без записи")

    add_arg(command, summary, "--page-size", page_size, f"Размер страницы: {page_size}")
    add_arg(command, summary, "--delay", delay, f"Пауза: {delay} сек")
    add_arg(command, summary, "--resume-page", resume_page, f"Продолжить со страницы: {resume_page}")
    add_arg(command, summary, "--retries", retries, f"Повторы сети: {retries}")
    add_arg(command, summary, "--retry-delay", retry_delay, f"Пауза повтора: {retry_delay} сек")

    run_command(command, summary)
    pause()


def cleanup_flow() -> None:
    clear()
    print(f"{COLORS['magenta']}> Очистка БД и папок актеров{COLORS['reset']}")
    print(f"{COLORS['dim']}Сначала лучше запускать preview. Удаление включается отдельным вопросом в конце.{COLORS['reset']}")
    command = [PYTHON, str(ROOT / "scripts" / "cleanup_actors.py")]
    filter_args, summary = common_filters(cleanup_mode=True)
    command += filter_args
    country_args, country_summary = country_filters()
    command += country_args
    summary += country_summary

    section("5. Безопасность удаления")
    if ask_yes_no(
        "Удалять строки с пустыми метаданными?",
        False,
        yes="опаснее: старые записи без scene_count/breast_type тоже могут удалиться",
        no="пустые метаданные оставить как есть",
    ):
        command.append("--include-unknown")
        summary.append("Пустые метаданные: тоже удалять")
    else:
        summary.append("Пустые метаданные: оставить")

    apply_delete = ask_yes_no(
        "Сразу применить удаление?",
        False,
        yes="реально удалить строки БД и папки",
        no="только preview, без изменений",
    )
    if apply_delete:
        command.append("--apply")
        summary.append("Режим: APPLY, удалить реально")
    else:
        summary.append("Режим: PREVIEW, ничего не удалять")

    run_command(command, summary, danger=apply_delete)
    pause()


def build_index_flow() -> None:
    clear()
    print(f"{COLORS['magenta']}> Сборка FAISS index{COLORS['reset']}\n")
    command = [PYTHON, str(ROOT / "scripts" / "build_index.py")]
    summary = ["Задача: пересобрать face-recognition index"]
    min_images = ask_int(
        "Минимум reference-фото у актера для попадания в index",
        4,
        hint="Актеры с меньшим числом фото будут пропущены. 1 = индексировать всех, у кого есть фото.",
    )
    add_arg(command, summary, "--min-images", min_images, f"Минимум фото на актера: {min_images}")
    if ask_yes_no(
        "Пересчитать все embeddings заново?",
        False,
        yes="дольше, но полностью обновит кеш",
        no="использовать кеш, если он есть",
    ):
        command.append("--refresh-cache")
        summary.append("Embeddings: пересчитать заново")
    else:
        summary.append("Embeddings: использовать кеш")
    run_command(command, summary)
    pause()


def cleanup_images_flow() -> None:
    clear()
    print(f"{COLORS['magenta']}> Cleanup reference photos{COLORS['reset']}\n")
    command = [PYTHON, str(ROOT / "scripts" / "cleanup_images.py")]
    summary = ["Задача: найти reference-фото без пригодного лица"]
    min_face_area = ask_float(
        "Минимальная площадь лица относительно фото",
        0.01,
        hint="0.01 = лицо занимает примерно 1% изображения. Больше = строже.",
    )
    add_arg(command, summary, "--min-face-area-ratio", min_face_area, f"Минимальная площадь лица: {min_face_area}")
    if ask_yes_no(
        "Удалять DB-строки, если файл фото отсутствует?",
        False,
        yes="строки с отсутствующими файлами попадут в удаление",
        no="пропустить отсутствующие файлы",
    ):
        command.append("--delete-missing")
        summary.append("Отсутствующие файлы: удалять строки")
    else:
        summary.append("Отсутствующие файлы: не трогать")

    apply_delete = ask_yes_no(
        "Сразу применить удаление?",
        False,
        yes="удалить файлы фото и строки actor_images",
        no="только preview, без изменений",
    )
    if apply_delete:
        command.append("--apply")
        summary.append("Режим: APPLY, удалить реально")
    else:
        summary.append("Режим: PREVIEW, ничего не удалять")

    run_command(command, summary, danger=apply_delete)
    pause()


def index_status_flow() -> None:
    clear()
    sys.path.insert(0, str(ROOT / "backend"))
    from config import settings  # noqa: PLC0415
    from database import actor_db  # noqa: PLC0415

    actors, total = actor_db.list_actors(page=1, page_size=1)
    faiss_path = settings.faiss_index_path
    id_map_path = settings.faiss_id_map_path
    print(f"{COLORS['magenta']}> Статус локальной базы и index{COLORS['reset']}\n")
    print(f"Актеров в БД: {total}")
    print(f"FAISS index: {faiss_path} ({'есть' if faiss_path.exists() else 'нет'})")
    print(f"FAISS ID map: {id_map_path} ({'есть' if id_map_path.exists() else 'нет'})")
    if actors:
        print(f"Пример записи: {actors[0]['name']}")
    pause()


def main() -> int:
    actions = [
        ("Scrape StashDB", "скачать новых актеров/актрис по фильтрам"),
        ("Backfill metadata", "обновить StashDB-данные у уже существующих записей"),
        ("Cleanup actors", "найти или удалить записи и папки, которые не проходят фильтры"),
        ("Cleanup photos", "найти или удалить reference-фото без лиц"),
        ("Build face index", "пересобрать FAISS index для распознавания лиц"),
        ("Index status", "показать количество записей и наличие index-файлов"),
        ("Exit", "закрыть меню"),
    ]

    while True:
        choice = menu("Что нужно сделать?", actions)
        if choice is None or choice == 6:
            return 0
        if choice == 0:
            scrape_flow(backfill=False)
        elif choice == 1:
            scrape_flow(backfill=True)
        elif choice == 2:
            cleanup_flow()
        elif choice == 3:
            cleanup_images_flow()
        elif choice == 4:
            build_index_flow()
        elif choice == 5:
            index_status_flow()


if __name__ == "__main__":
    raise SystemExit(main())
