"""Проверки поставляемого config.json.

Поведение программы живёт не только в коде: порядок категорий и списки слов в
config.json решают не меньше. Все случаи ниже — настоящие файлы из загрузок,
на которых переразложение однажды сработало неверно. Тесты держат эти границы,
чтобы правка конфига не сломала их молча.
"""
import re
from pathlib import Path

import pytest

from sorter.classifier import classify
from sorter.config import Config

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@pytest.fixture(scope="module")
def cfg() -> Config:
    # Без my_rules.json: снимок проверяет правила программы, а правки человека
    # в папке разработчика ломали бы его на его машине.
    config = Config.load(CONFIG_PATH, user=False)
    config.overrides = {}  # правила проверяем отдельно, тут интересны сами слова
    return config


def category(cfg: Config, name: str) -> str:
    return classify(name, "", cfg)[0]


# --- регрессии переразложения: файл лежал верно, а правила его забирали ---


@pytest.mark.parametrize(
    "name, expected",
    [
        # CAD-формат: слово «launcher» уводило деталь в Игры
        ("Puck_Launcher.step", "3D"),
        # LTX-Video — модель генерации видео, ролики демоted в Others
        ("LTX_2.3_ia2v_00001_.mp4", "AI"),
        # исходники страниц уезжали из Кода в Others
        ("liquid-glass.html", "Dev"),
        ("coffee-site.html", "Dev"),
        ("workflow.json", "Dev"),
        # BeamMP — мультиплеер для BeamNG, слово «installer» уводило в Программы
        ("BeamMP_Installer.exe", "Games"),
        # безымянный .exe должен остаться программой, а не упасть в Others
        ("RadGen.exe", "Apps"),
    ],
)
def test_resort_does_not_demote_correctly_placed_file(cfg, name, expected):
    assert category(cfg, name) == expected


# --- порядок категорий ---


def test_electronics_wins_over_programs(cfg):
    """Иначе слово `driver` забирает драйвер платы CH340 себе."""
    assert category(cfg, "driver_ch340_341.zip") == "Electronics"


def test_programs_win_over_media(cfg):
    """Иначе слово `music` уводит установщик плеера в музыку."""
    assert category(cfg, "Yandex_Music_x64_5.92.1.exe") == "Apps"


def test_study_wins_over_documents(cfg):
    assert category(cfg, "Памятки_к_экзамену_9_класс.pdf") == "Study"


def test_contract_goes_to_documents(cfg):
    assert category(cfg, "Dop._soglashenie_k_dogovoru___U-1570-25.docx") == "Docs"


# --- шаблоны имён ---


def test_frame_range_is_a_render(cfg):
    assert category(cfg, "0001-0250.mp4") == "3D"


def test_bare_date_name_is_a_clip(cfg):
    assert category(cfg, "0606.mp4") == "Media"


def test_telegram_photo_is_a_screenshot(cfg):
    assert category(cfg, "photo_2026-06-19_20-03-13.jpg") == "Screenshots"


# --- давние ловушки ---


def test_font_lora_is_not_an_ai_model(cfg):
    """Шрифт Lora не имеет отношения к LoRA."""
    assert category(cfg, "Lora-Regular.ttf") == "Design"


@pytest.mark.parametrize(
    "name",
    [
        "Расписание_новое.docx",
        "расписание.pdf",
        "Расписание 2 семестр.xlsx",
        "новое расписание уроков.docx",
        "РАСПИСАНИЕ.PDF",
        "raspisanie_2026.pdf",
    ],
)
def test_schedule_goes_to_studies(cfg, name):
    """Расписание — это учёба, а оно уезжало в Others как неопознанное.

    Слово взято основой (`расписан`), потому что склоняется: расписание,
    расписания, расписанию. Транслитерация рядом — так устроены все пары в этих
    правилах, и имя `raspisanie_2026.pdf` приходит с сайтов так же часто.
    """
    assert category(cfg, name) == "Study"


@pytest.mark.parametrize(
    "name",
    ["расписка о получении.pdf", "расписной поднос.jpg", "Роспись стен.png"],
)
def test_schedule_word_does_not_catch_its_neighbours(cfg, name):
    """Соседи по корню — не расписание.

    Основа обрывается на `расписан` нарочно: `распис` забрал бы и расписку, и
    расписной поднос, а Учёба стоит первой категорией и выигрывает у всех.
    """
    assert category(cfg, name) != "Study"


def test_managed_folders_cover_all_categories(cfg):
    """Иначе переразложение не зайдёт в папку собственной категории."""
    missing = (set(cfg.categories) | {cfg.fallback_category}) - set(cfg.managed_folders)
    assert not missing


def test_managed_folders_cover_all_types(cfg):
    missing = (set(cfg.type_map) | {cfg.fallback_type}) - set(cfg.managed_folders)
    assert not missing


# --- расширения, названные в type_map, но забытые в словах категории ---


@pytest.mark.parametrize(
    "name, expected",
    [
        # `.stl` стоит и в type_map["3D"], и в external_3d.extensions — то есть
        # программа знает, что это 3D, — а слова в категории не было, и модель
        # с нейтральным именем уезжала в Others при снятой галочке выноса.
        ("деталь.stl", "3D"),
        ("model.fbx", "3D"),
        ("макет.psd", "Design"),
        ("скрипт.js", "Dev"),
        # `.cpp` и `.java` стоят в type_map["Code"] — программа знает, что это
        # исходники, и всё равно клала их в `Others/Code`: слова в категории
        # «Код» не было, а соседние `.py`, `.js`, `.ts`, `.html` были. Снаружи
        # это выглядит как «не опознан», хотя тип опознан безошибочно.
        ("main.cpp", "Dev"),
        ("Hello.java", "Dev"),
    ],
)
def test_extension_known_to_type_map_is_known_to_a_category(cfg, name, expected):
    assert category(cfg, name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        # `.c` в слова категории не добавлен нарочно: слова ищутся вхождением
        # подстроки, а «.c» входит в «.css», «.csv» и в любое имя с «.com».
        # Одна такая запись увела бы в «Код» половину загрузок — ровно тот
        # случай, ради которого пустую строку в списке слов выбрасывают.
        ("таблица.csv", "Others"),
        ("style.css", "Dev"),
    ],
)
def test_short_extension_words_do_not_swallow_neighbours(cfg, name, expected):
    assert category(cfg, name) == expected


def test_every_external_3d_extension_is_a_3d_keyword(cfg):
    """Список выноса 3D и слова категории «3D» должны говорить одно и то же.

    Иначе галочка «3D → отдельная папка» меняет не только место, но и саму
    категорию файла: с ней `деталь.stl` — модель, без неё — «не опознан».
    """
    words = {w.lower() for w in cfg.categories["3D"] if w.startswith(".")}
    missing = {f".{e.lower()}" for e in cfg.external_3d.get("extensions", [])} - words
    assert not missing, f"расширения выноса 3D нет в словах категории: {missing}"


# --- слова-обрубки, забиравшие соседей по подстроке ---


@pytest.mark.parametrize(
    "name, expected",
    [
        # `фон` стояло в словах категории «3D» и ловилось подстрокой, то есть
        # хвостом любого слова: телефон, микрофон, диктофон — и началом:
        # фонарь, фонд, фонтан, фонотека. Для русской папки загрузок это не
        # редкий случай, а ежедневный, и раскладка при этом честно пишет
        # «слово» — та самая пометка, которой README велит доверять.
        ("инструкция_телефон.pdf", "Others"),
        ("Телефонный справочник.xlsx", "Others"),
        ("микрофон-обзор.mp4", "Others"),
        ("Фонд помощи.docx", "Others"),
        ("фонотека.m3u", "Others"),
        # `иво` из «Учёбы» забирало «живой» и «оливье»
        ("живой концерт.mp3", "Others"),
        ("оливье рецепт.txt", "Others"),
        # `sim` из «Кода» забирало assimp и basim
        ("assimp-5.4.zip", "Others"),
        ("basim.png", "Others"),
    ],
)
def test_short_stem_does_not_grab_the_middle_of_a_word(cfg, name, expected):
    assert category(cfg, name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        # …а сам смысл слова сохранён: границы даёт `patterns`, потому что
        # ключевые слова умеют только вхождение подстроки.
        ("фон.png", "3D"),
        ("фон_лес.jpg", "3D"),
        ("студийный фон.hdr", "3D"),
        ("фон2.png", "3D"),
        ("ИВО 2026.pdf", "Study"),
        ("ИВО2026.pdf", "Study"),
        ("виво разбор.pdf", "Study"),
        ("зиво.pdf", "Study"),
        ("os_sim.py", "Dev"),
        ("sim-city.exe", "Dev"),
    ],
)
def test_whole_word_stem_still_wins(cfg, name, expected):
    assert category(cfg, name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        # Шаблоны бьют раньше ключевых слов, поэтому слова с границами
        # переехали в конец `patterns` — за якорные выражения. Иначе
        # безымянный `фон` в имени снимка забирал бы снимок себе.
        ("Снимок экрана 2026 фон.png", "Screenshots"),
        ("photo_2026-06-19_20-03-13 фон.jpg", "Screenshots"),
        # …а сами якорные выражения от перестановки не сдвинулись
        ("0001-0250.mp4", "3D"),
        ("0606.mp4", "Media"),
        ("audio-2026-01-02-lecture.mp3", "Media"),
    ],
)
def test_anchored_patterns_still_win_over_word_patterns(cfg, name, expected):
    assert category(cfg, name) == expected


def test_mid_word_match_is_still_allowed_where_it_is_right(cfg):
    """Границы слова — точечная правка, а не общее правило.

    В настоящих загрузках подстрока в середине слова почти всегда права:
    `ChromeSetup.exe`, `48RXF1.scs`, `BearVPN_2.7.0.exe`, `LegacyLauncher.exe`,
    `WindowsAppRuntimeInstall-x64.exe`, `3DBenchy_PLA0.25.mp4` — всё это
    опознано хвостом слова и опознано верно. Поэтому границы получили ровно
    три обрубка, а не весь список.
    """
    assert category(cfg, "ChromeSetup.exe") == "Apps"
    assert category(cfg, "48RXF1.scs") == "Games"
    assert category(cfg, "BearVPN_2.7.0.exe") == "Apps"
    assert category(cfg, "LegacyLauncher.exe") == "Games"
    assert category(cfg, "WindowsAppRuntimeInstall-x64.exe") == "Apps"


# --- правила-призраки: запись есть, а до неё не доходит очередь ---


def test_micropython_is_not_shadowed_by_python(cfg):
    """`micropython` стояло словом в «Электронике» и не срабатывало никогда.

    Слова перебираются по категориям, а «Код» стоит выше «Электроники» — и
    `python` внутри `micropython` забирал прошивку себе. Запись при этом
    выглядела рабочей: строка в файле есть, ошибок нет, а прошивка ESP32
    уезжала в «Код» с честной пометкой «слово». Тот же случай, что у `фон`,
    `иво` и `sim`, только наоборот: мешает не хвост чужого слова, а собственная
    середина. Лечится тем же — переездом в `patterns`, которые бьют раньше слов.
    """
    assert category(cfg, "micropython-esp32-20240105.bin") == "Electronics"
    assert category(cfg, "MicroPython_v1.24.uf2") == "Electronics"
    # а сам «Код» на месте: обычный питон никуда не переехал
    assert category(cfg, "python-3.12.4-amd64.exe") == "Dev"


def test_no_extension_is_named_in_two_types(cfg):
    """Второй тип для того же расширения — мёртвая запись.

    `match_type` отдаёт первый подошедший, поэтому `exr` в `type_map["3D"]`
    рядом с `exr` в `Images` не работал никогда. Проверку держит и `Config`
    (жалоба при чтении), здесь — сами поставляемые правила.
    """
    seen = {}
    for type_name, extensions in cfg.type_map.items():
        for value in extensions:
            key = str(value).lower()
            assert key not in seen, (
                f"«{value}» названо и в «{seen.get(key)}», и в «{type_name}»")
            seen[key] = type_name


def test_shipped_rules_read_without_complaints():
    """Поставляемые правила должны читаться без единой жалобы.

    Проверки `Config` (битые регулярки, категории мимо `managed_folders`,
    расширение в двух типах) писались по настоящим поломкам в этом самом файле.
    Молчание при чтении — их итог.
    """
    config = Config.load(CONFIG_PATH, user=False)
    assert config.problems == []


_CYRILLIC = re.compile("[а-яёА-ЯЁ]")


def test_category_folders_have_english_names():
    """Папки категорий в загрузках - латиницей (Алексей, 24.10.2026).

    Русские имена (`Учёба`, `Программы`, ...) ему не нравились на вид, и с
    правил 24.10 категории называются по-английски: Study, Docs, AI, Dev,
    Electronics, 3D, Games, Design, Apps, Media, Screenshots, запасная Others.
    Имя категории - это имя папки на диске, поэтому проверяем все места, откуда
    оно туда попадает: категории, шаблоны, ручные правила, `managed_folders`,
    запасную категорию. Ручное правило со старым русским именем создало бы
    рядом с `Apps` вторую папку `Программы`.
    """
    config = Config.load(CONFIG_PATH, user=False)
    names = {
        "categories": list(config.categories),
        "patterns": list(config.patterns),
        "overrides": sorted(set(config.overrides.values())),
        "managed_folders": list(config.managed_folders),
        "fallback_category": [config.fallback_category],
    }
    russian = {where: [n for n in values if _CYRILLIC.search(n)]
               for where, values in names.items()}
    assert {k: v for k, v in russian.items() if v} == {}
    # Ручные правила ведут только в существующие категории.
    known = set(config.categories) | {config.fallback_category}
    assert set(config.overrides.values()) <= known
