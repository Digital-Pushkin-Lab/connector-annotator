"""Gradio Blocks layout: builds the UI and wires widgets to callbacks."""

import gradio as gr

from .batch import BATCH_UPLOAD_LABEL, _progress_html, process_folder, request_stop
from .callbacks import (
    add_by_phrase,
    add_by_position,
    analyze_text,
    delete_highlight,
    on_select_highlight,
    update_highlight,
)
from .config import (
    CATEGORY_CHOICES,
    CSS,
    NO_SEMFIELD,
    PRAGMATICS_CHOICES,
    SEMFIELD1_CHOICES,
    SEMFIELD2_CHOICES,
)
from .file_io import UPLOAD_FILE_TYPES, UPLOAD_LABEL, load_file
from .xml_io import save_xml


def build_single_text_tab():
    state_text = gr.State("")
    state_highlights = gr.State([])

    with gr.Row():
        with gr.Column(scale=1):
            input_box = gr.Textbox(
                label="Исходный текст",
                placeholder="Введите текст здесь…",
                lines=10,
            )
            upload_file = gr.File(
                label=UPLOAD_LABEL,
                file_types=UPLOAD_FILE_TYPES,
                type="filepath",
            )
            analyze_btn = gr.Button("Анализировать", variant="primary")

            gr.Markdown("### Добавить разметку")
            with gr.Tabs():
                with gr.TabItem("По позициям"):
                    add_start = gr.Number(label="Начало (символ)", precision=0, minimum=0)
                    add_end = gr.Number(label="Конец (символ)", precision=0, minimum=0)
                    add_label_pos = gr.Textbox(label="Название коннектора", placeholder="например, если… то")
                    add_category_pos = gr.Dropdown(
                        label="Тип",
                        choices=CATEGORY_CHOICES,
                        value=NO_SEMFIELD,
                    )
                    add_semfield1_pos = gr.Dropdown(
                        label="Основное значение (semfield1)",
                        info="Альтернативы через «;» — можно оставить одну или несколько.",
                        choices=SEMFIELD1_CHOICES,
                        value=NO_SEMFIELD,
                        allow_custom_value=True,
                    )
                    add_semfield2_pos = gr.Dropdown(
                        label="Сопроводительное значение (облигаторное)",
                        info="Набор через «,» — сопровождает основное значение.",
                        choices=SEMFIELD2_CHOICES,
                        value=NO_SEMFIELD,
                        allow_custom_value=True,
                    )
                    add_pragmatics_pos = gr.Dropdown(
                        label="Прагматическая установка (облигаторная)",
                        info="Набор через «,».",
                        choices=PRAGMATICS_CHOICES,
                        value=NO_SEMFIELD,
                        allow_custom_value=True,
                    )
                    add_pos_btn = gr.Button("Добавить разметку")

                with gr.TabItem("По фразе"):
                    add_phrase = gr.Textbox(label="Фраза", placeholder="Введите точную фразу из текста")
                    add_label_phrase = gr.Textbox(label="Название коннектора", placeholder="например, если… то")
                    add_category_phrase = gr.Dropdown(
                        label="Тип",
                        choices=CATEGORY_CHOICES,
                        value=NO_SEMFIELD,
                    )
                    add_semfield1_phrase = gr.Dropdown(
                        label="Основное значение (semfield1)",
                        info="Альтернативы через «;» — можно оставить одну или несколько.",
                        choices=SEMFIELD1_CHOICES,
                        value=NO_SEMFIELD,
                        allow_custom_value=True,
                    )
                    add_semfield2_phrase = gr.Dropdown(
                        label="Сопроводительное значение (облигаторное)",
                        info="Набор через «,» — сопровождает основное значение.",
                        choices=SEMFIELD2_CHOICES,
                        value=NO_SEMFIELD,
                        allow_custom_value=True,
                    )
                    add_pragmatics_phrase = gr.Dropdown(
                        label="Прагматическая установка (облигаторная)",
                        info="Набор через «,».",
                        choices=PRAGMATICS_CHOICES,
                        value=NO_SEMFIELD,
                        allow_custom_value=True,
                    )
                    add_phrase_btn = gr.Button("Найти и добавить")

            gr.Markdown("### Изменить или удалить")
            hl_select = gr.Dropdown(label="Выбранная разметка", choices=[])
            edit_start = gr.Number(label="Начало", precision=0, minimum=0)
            edit_end = gr.Number(label="Конец", precision=0, minimum=0)
            edit_label = gr.Textbox(label="Название коннектора")
            edit_category = gr.Dropdown(
                label="Тип",
                choices=CATEGORY_CHOICES,
                value=NO_SEMFIELD,
            )
            edit_semfield1 = gr.Dropdown(
                label="Основное значение (semfield1)",
                info="Альтернативы через «;» — можно оставить одну или несколько.",
                choices=SEMFIELD1_CHOICES,
                value=NO_SEMFIELD,
                allow_custom_value=True,
            )
            edit_semfield2 = gr.Dropdown(
                label="Сопроводительное значение (облигаторное)",
                info="Набор через «,» — сопровождает основное значение. Можно править вручную.",
                choices=SEMFIELD2_CHOICES,
                value=NO_SEMFIELD,
                allow_custom_value=True,
            )
            edit_pragmatics = gr.Dropdown(
                label="Прагматическая установка (облигаторная)",
                info="Набор через «,». Можно править вручную.",
                choices=PRAGMATICS_CHOICES,
                value=NO_SEMFIELD,
                allow_custom_value=True,
            )
            with gr.Row():
                update_btn = gr.Button("Изменить границы / название / значения")
                delete_btn = gr.Button("Удалить разметку", variant="stop")

            save_btn = gr.Button("Сохранить разметку как XML", variant="secondary")

            gr.Examples(
                examples=[
                    ["Не оставь меня ни мертвым, ни раненым."],
                    ["До тех пор, пока не выработается привычка."],
                    ["А в то же время он не хотел уходить."],
                    ["Если ты придёшь, то я буду рад, а если нет — тоже хорошо."],
                ],
                inputs=input_box,
                label="Примеры",
            )

        with gr.Column(scale=1):
            output_html = gr.HTML(label="Размеченный текст")
            output_table = gr.Markdown(label="Текущая разметка", elem_classes="scrollable-table")
            output_stats = gr.Markdown(label="Статистика")
            output_file = gr.File(label="XML-файл")
            msg_box = gr.Textbox(label="Сообщения", interactive=False)

    # ---- wire events ----
    upload_file.upload(
        fn=load_file,
        inputs=[upload_file, state_text, state_highlights],
        outputs=[input_box, output_html, output_table, hl_select, output_stats, state_text, state_highlights, msg_box],
    )

    analyze_btn.click(
        fn=analyze_text,
        inputs=input_box,
        outputs=[output_html, output_table, hl_select, output_stats, state_text, state_highlights, msg_box],
    )

    add_pos_btn.click(
        fn=add_by_position,
        inputs=[
            state_text, state_highlights, add_start, add_end, add_label_pos,
            add_semfield1_pos, add_semfield2_pos, add_pragmatics_pos, add_category_pos,
        ],
        outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
    )

    add_phrase_btn.click(
        fn=add_by_phrase,
        inputs=[
            state_text, state_highlights, add_phrase, add_label_phrase,
            add_semfield1_phrase, add_semfield2_phrase, add_pragmatics_phrase, add_category_phrase,
        ],
        outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
    )

    hl_select.change(
        fn=on_select_highlight,
        inputs=[state_text, state_highlights, hl_select],
        outputs=[edit_start, edit_end, edit_label, edit_semfield1, edit_semfield2, edit_pragmatics, edit_category],
    )

    update_btn.click(
        fn=update_highlight,
        inputs=[
            state_text, state_highlights, hl_select, edit_start, edit_end, edit_label,
            edit_semfield1, edit_semfield2, edit_pragmatics, edit_category,
        ],
        outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
    )

    delete_btn.click(
        fn=delete_highlight,
        inputs=[state_text, state_highlights, hl_select],
        outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
    )

    save_btn.click(
        fn=save_xml,
        inputs=[state_text, state_highlights],
        outputs=[output_file, msg_box],
    )


def build_batch_tab():
    gr.Markdown(
        "Загрузите папку с текстами — каждый подходящий файл будет "
        "проанализирован тем же алгоритмом, что и на вкладке «Разметка "
        "текста», и превращён в отдельный XML-файл. Файлы других форматов "
        "пропускаются."
    )

    with gr.Row():
        with gr.Column(scale=1):
            folder_upload = gr.File(
                label=BATCH_UPLOAD_LABEL,
                file_count="directory",
                type="filepath",
                height=280,
            )
            process_btn = gr.Button("Обработать папку", variant="primary")

        with gr.Column(scale=1):
            with gr.Row():
                progress_html = gr.HTML(_progress_html(0, 0, "Ожидание"))
                stop_btn = gr.Button("Остановить", variant="stop", scale=0)
            with gr.Row(visible=False) as confirm_row:
                gr.Markdown("Точно остановить обработку?")
                confirm_stop_btn = gr.Button("Да, остановить", variant="stop", scale=0)
                cancel_stop_btn = gr.Button("Нет", scale=0)
            console_box = gr.Textbox(
                label="Консоль",
                lines=18,
                max_lines=30,
                interactive=False,
                autoscroll=True,
            )
            batch_output_files = gr.File(label="Результаты (XML)", file_count="multiple", height=280)
            batch_zip_file = gr.File(label="Скачать всё (ZIP)")

    process_btn.click(
        fn=process_folder,
        inputs=[folder_upload],
        outputs=[console_box, batch_output_files, batch_zip_file, progress_html],
    )

    # Stop button opens an inline yes/no confirmation instead of a blocking
    # browser confirm() dialog: a native confirm() froze the queue's SSE
    # connection for this session and crashed it. Stopping itself is a
    # cooperative flag (app.batch.request_stop), not Gradio's `cancels=`:
    # cancelling this generator's own SSE-owning event crashed the same
    # connection ("404: Session not found") once the browser reconnected.
    stop_btn.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=False)),
        outputs=[confirm_row, stop_btn],
    )

    confirm_stop_btn.click(
        fn=request_stop,
        inputs=None,
        outputs=None,
    ).then(
        fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
        outputs=[confirm_row, stop_btn],
    )

    cancel_stop_btn.click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
        outputs=[confirm_row, stop_btn],
    )


def main():
    with gr.Blocks(css=CSS, title="Аннотатор коннекторов") as demo:
        gr.Markdown("# Аннотатор коннекторов")

        with gr.Tabs():
            with gr.TabItem("Разметка текста"):
                gr.Markdown(
                    "Вставьте текст на русском языке и нажмите **Анализировать**. "
                    "Найденные линкеры подсвечены оранжевым, вводные слова — зелёным, "
                    "ручная разметка — синим. "
                    "Наведите курсор на фрагмент, чтобы увидеть название коннектора."
                )
                build_single_text_tab()

            with gr.TabItem("Пакетная обработка"):
                build_batch_tab()

    demo.launch(share=True)
