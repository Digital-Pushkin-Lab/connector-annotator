"""All interface captions in one place: widget labels, hints, placeholders,
button and tab names, table/statistics headings.

To rename something in the UI, change it here -- the rest of the app only
refers to these names. Status messages shown in the "Сообщения" box and the
batch console still live next to the code that produces them
(callbacks.py, file_io.py, xml_io.py, batch.py, highlights.py).
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Connector meaning fields: semfield1 / semfield2 / pragmatics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldLabels:
    label: str           # dropdown caption (add / edit forms)
    info: str            # hint under the dropdown in the "add" forms
    info_edit: str       # hint under the dropdown in the "edit" form
    table_header: str    # column header in the "Текущая разметка" table
    stats_heading: str   # heading of this field's breakdown in "Статистика"


SEMFIELD1 = FieldLabels(
    label="Основное значение (semfield1)",
    info="Альтернативы через «;» — можно оставить одну или несколько.",
    info_edit="Альтернативы через «;» — можно оставить одну или несколько.",
    table_header="основное значение",
    stats_heading="По основному значению (semfield1)",
)

SEMFIELD2 = FieldLabels(
    label="Сопроводительное значение (облигаторное)",
    info="Набор через «,» — сопровождает основное значение.",
    info_edit="Набор через «,» — сопровождает основное значение. Можно править вручную.",
    table_header="сопроводительное значение",
    stats_heading="По сопроводительному значению (semfield2)",
)

PRAGMATICS = FieldLabels(
    label="Прагматическая установка (облигаторная)",
    info="Набор через «,».",
    info_edit="Набор через «,». Можно править вручную.",
    table_header="прагматическая установка",
    stats_heading="По прагматической установке",
)

# Shown in a meaning dropdown / table cell when the field is empty. It is
# filtered out when the field is read back and never written to XML (empty
# fields are saved as ""), so it is safe to rename.
NO_SEMFIELD = "не выбрано"


# ---------------------------------------------------------------------------
# Page header and tabs
# ---------------------------------------------------------------------------

APP_TITLE = "Аннотатор коннекторов"
TAB_SINGLE_TEXT = "Разметка текста"
TAB_BATCH = "Пакетная обработка"

SINGLE_TEXT_INTRO = (
    "Вставьте текст на русском языке и нажмите **Анализировать**. "
    "Найденные линкеры подсвечены оранжевым, "
    "ручная разметка — синим. "
    "Наведите курсор на фрагмент, чтобы увидеть название коннектора."
)


# ---------------------------------------------------------------------------
# "Разметка текста" tab: input
# ---------------------------------------------------------------------------

INPUT_TEXT = "Исходный текст"
INPUT_TEXT_PLACEHOLDER = "Введите текст здесь…"
ANALYZE_BUTTON = "Анализировать"

# File upload caption; the .doc variant depends on catdoc being installed.
UPLOAD_FILE_WITH_DOC = "Загрузить файл (.txt, .docx, .doc — текст; .xml — готовая разметка)"
UPLOAD_FILE_WITHOUT_DOC = (
    "Загрузить файл (.txt, .docx — текст; .xml — готовая разметка). "
    ".doc не поддерживается на этом сервере (нет catdoc) — сохраните как .docx"
)

EXAMPLES = "Примеры"


# ---------------------------------------------------------------------------
# "Разметка текста" tab: adding markup
# ---------------------------------------------------------------------------

ADD_SECTION_HEADING = "### Добавить разметку"
ADD_BY_POSITION_TAB = "По позициям"
ADD_BY_PHRASE_TAB = "По фразе"

ADD_START = "Начало (символ)"
ADD_END = "Конец (символ)"
PHRASE = "Фраза"
PHRASE_PLACEHOLDER = "Введите точную фразу из текста"

CONNECTOR_NAME = "Название коннектора"
CONNECTOR_NAME_PLACEHOLDER = "например, если… то"

ADD_BY_POSITION_BUTTON = "Добавить разметку"
ADD_BY_PHRASE_BUTTON = "Найти и добавить"


# ---------------------------------------------------------------------------
# "Разметка текста" tab: editing / deleting markup
# ---------------------------------------------------------------------------

EDIT_SECTION_HEADING = "### Изменить или удалить"
SELECTED_MARKUP = "Выбранная разметка"
EDIT_START = "Начало"
EDIT_END = "Конец"
UPDATE_BUTTON = "Изменить границы / название / значения"
DELETE_BUTTON = "Удалить разметку"
SAVE_XML_BUTTON = "Сохранить разметку как XML"


# ---------------------------------------------------------------------------
# "Разметка текста" tab: output column
# ---------------------------------------------------------------------------

OUTPUT_HTML = "Размеченный текст"
OUTPUT_TABLE = "Текущая разметка"
OUTPUT_STATS = "Статистика"
OUTPUT_XML_FILE = "XML-файл"
MESSAGES = "Сообщения"

# "Текущая разметка" table: columns other than the three meaning fields
TABLE_HEADER_CONNECTOR_NAME = "название коннектора"
TABLE_HEADER_TEXT = "текст"
TABLE_EMPTY = "_Разметка отсутствует_"

STATS_TOTAL = "Всего коннекторов"
STATS_EMPTY = "_Нет данных для статистики_"


# ---------------------------------------------------------------------------
# "Пакетная обработка" tab
# ---------------------------------------------------------------------------

BATCH_INTRO = (
    "Загрузите папку с текстами — каждый подходящий файл будет "
    "проанализирован тем же алгоритмом, что и на вкладке «Разметка "
    "текста», и превращён в отдельный XML-файл. Файлы других форматов "
    "пропускаются."
)

# Folder upload caption; the .doc variant depends on catdoc being installed.
BATCH_UPLOAD_WITH_DOC = "Загрузите папку с файлами (.txt, .docx, .doc) — остальные форматы будут пропущены"
BATCH_UPLOAD_WITHOUT_DOC = (
    "Загрузите папку с файлами (.txt, .docx) — остальные форматы будут пропущены"
    "; .doc не поддерживается на этом сервере (нет catdoc)"
)

PROCESS_FOLDER_BUTTON = "Обработать папку"
STOP_BUTTON = "Остановить"
STOP_CONFIRM_QUESTION = "Точно остановить обработку?"
STOP_CONFIRM_YES = "Да, остановить"
STOP_CONFIRM_NO = "Нет"
PROGRESS_IDLE = "Ожидание"
CONSOLE = "Консоль"
BATCH_RESULT_FILES = "Результаты (XML)"
BATCH_ZIP_FILE = "Скачать всё (ZIP)"
