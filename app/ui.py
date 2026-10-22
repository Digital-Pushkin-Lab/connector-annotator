"""Gradio Blocks layout: builds the UI and wires widgets to callbacks."""

from typing import List

import gradio as gr

from . import labels
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
    CSS,
    NO_SEMFIELD,
    PRAGMATICS_CHOICES,
    SEMFIELD1_CHOICES,
    SEMFIELD2_CHOICES,
)
from .file_io import UPLOAD_FILE_TYPES, UPLOAD_LABEL, load_file
from .xml_io import save_xml


def _meaning_dropdown(field: labels.FieldLabels, choices: List[str], editing: bool = False):
    """Dropdown for one meaning field (semfield1 / semfield2 / pragmatics)."""
    return gr.Dropdown(
        label=field.label,
        info=field.info_edit if editing else field.info,
        choices=choices,
        value=NO_SEMFIELD,
        allow_custom_value=True,
    )


def build_single_text_tab():
    state_text = gr.State("")
    state_highlights = gr.State([])

    with gr.Row():
        with gr.Column(scale=1):
            input_box = gr.Textbox(
                label=labels.INPUT_TEXT,
                placeholder=labels.INPUT_TEXT_PLACEHOLDER,
                lines=10,
            )
            upload_file = gr.File(
                label=UPLOAD_LABEL,
                file_types=UPLOAD_FILE_TYPES,
                type="filepath",
            )
            analyze_btn = gr.Button(labels.ANALYZE_BUTTON, variant="primary")

            gr.Markdown(labels.ADD_SECTION_HEADING)
            with gr.Tabs():
                with gr.TabItem(labels.ADD_BY_POSITION_TAB):
                    add_start = gr.Number(label=labels.ADD_START, precision=0, minimum=0)
                    add_end = gr.Number(label=labels.ADD_END, precision=0, minimum=0)
                    add_label_pos = gr.Textbox(label=labels.CONNECTOR_NAME, placeholder=labels.CONNECTOR_NAME_PLACEHOLDER)
                    add_semfield1_pos = _meaning_dropdown(labels.SEMFIELD1, SEMFIELD1_CHOICES)
                    add_semfield2_pos = _meaning_dropdown(labels.SEMFIELD2, SEMFIELD2_CHOICES)
                    add_pragmatics_pos = _meaning_dropdown(labels.PRAGMATICS, PRAGMATICS_CHOICES)
                    add_pos_btn = gr.Button(labels.ADD_BY_POSITION_BUTTON)

                with gr.TabItem(labels.ADD_BY_PHRASE_TAB):
                    add_phrase = gr.Textbox(label=labels.PHRASE, placeholder=labels.PHRASE_PLACEHOLDER)
                    add_label_phrase = gr.Textbox(label=labels.CONNECTOR_NAME, placeholder=labels.CONNECTOR_NAME_PLACEHOLDER)
                    add_semfield1_phrase = _meaning_dropdown(labels.SEMFIELD1, SEMFIELD1_CHOICES)
                    add_semfield2_phrase = _meaning_dropdown(labels.SEMFIELD2, SEMFIELD2_CHOICES)
                    add_pragmatics_phrase = _meaning_dropdown(labels.PRAGMATICS, PRAGMATICS_CHOICES)
                    add_phrase_btn = gr.Button(labels.ADD_BY_PHRASE_BUTTON)

            gr.Markdown(labels.EDIT_SECTION_HEADING)
            hl_select = gr.Dropdown(label=labels.SELECTED_MARKUP, choices=[])
            edit_start = gr.Number(label=labels.EDIT_START, precision=0, minimum=0)
            edit_end = gr.Number(label=labels.EDIT_END, precision=0, minimum=0)
            edit_label = gr.Textbox(label=labels.CONNECTOR_NAME)
            edit_semfield1 = _meaning_dropdown(labels.SEMFIELD1, SEMFIELD1_CHOICES, editing=True)
            edit_semfield2 = _meaning_dropdown(labels.SEMFIELD2, SEMFIELD2_CHOICES, editing=True)
            edit_pragmatics = _meaning_dropdown(labels.PRAGMATICS, PRAGMATICS_CHOICES, editing=True)
            with gr.Row():
                update_btn = gr.Button(labels.UPDATE_BUTTON)
                delete_btn = gr.Button(labels.DELETE_BUTTON, variant="stop")

            save_btn = gr.Button(labels.SAVE_XML_BUTTON, variant="secondary")

            gr.Examples(
                examples=[
                    ["Не оставь меня ни мертвым, ни раненым."],
                    ["До тех пор, пока не выработается привычка."],
                    ["А в то же время он не хотел уходить."],
                    ["Без сомненья, если ты придёшь, то я буду рад, но если нет — тоже хорошо."],
                ],
                inputs=input_box,
                label=labels.EXAMPLES,
            )

        with gr.Column(scale=1):
            output_html = gr.HTML(label=labels.OUTPUT_HTML)
            output_table = gr.Markdown(label=labels.OUTPUT_TABLE, elem_classes="scrollable-table")
            output_stats = gr.Markdown(label=labels.OUTPUT_STATS)
            output_file = gr.File(label=labels.OUTPUT_XML_FILE)
            msg_box = gr.Textbox(label=labels.MESSAGES, interactive=False)

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
            add_semfield1_pos, add_semfield2_pos, add_pragmatics_pos,
        ],
        outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
    )

    add_phrase_btn.click(
        fn=add_by_phrase,
        inputs=[
            state_text, state_highlights, add_phrase, add_label_phrase,
            add_semfield1_phrase, add_semfield2_phrase, add_pragmatics_phrase,
        ],
        outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
    )

    hl_select.change(
        fn=on_select_highlight,
        inputs=[state_text, state_highlights, hl_select],
        outputs=[edit_start, edit_end, edit_label, edit_semfield1, edit_semfield2, edit_pragmatics],
    )

    update_btn.click(
        fn=update_highlight,
        inputs=[
            state_text, state_highlights, hl_select, edit_start, edit_end, edit_label,
            edit_semfield1, edit_semfield2, edit_pragmatics,
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
    gr.Markdown(labels.BATCH_INTRO)

    with gr.Row():
        with gr.Column(scale=1):
            folder_upload = gr.File(
                label=BATCH_UPLOAD_LABEL,
                file_count="directory",
                type="filepath",
                height=280,
            )
            process_btn = gr.Button(labels.PROCESS_FOLDER_BUTTON, variant="primary")

        with gr.Column(scale=1):
            with gr.Row():
                progress_html = gr.HTML(_progress_html(0, 0, labels.PROGRESS_IDLE))
                stop_btn = gr.Button(labels.STOP_BUTTON, variant="stop", scale=0)
            with gr.Row(visible=False) as confirm_row:
                gr.Markdown(labels.STOP_CONFIRM_QUESTION)
                confirm_stop_btn = gr.Button(labels.STOP_CONFIRM_YES, variant="stop", scale=0)
                cancel_stop_btn = gr.Button(labels.STOP_CONFIRM_NO, scale=0)
            console_box = gr.Textbox(
                label=labels.CONSOLE,
                lines=18,
                max_lines=30,
                interactive=False,
                autoscroll=True,
            )
            batch_output_files = gr.File(label=labels.BATCH_RESULT_FILES, file_count="multiple", height=280)
            batch_zip_file = gr.File(label=labels.BATCH_ZIP_FILE)

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
    with gr.Blocks(css=CSS, title=labels.APP_TITLE) as demo:
        gr.Markdown(f"# {labels.APP_TITLE}")

        with gr.Tabs():
            with gr.TabItem(labels.TAB_SINGLE_TEXT):
                gr.Markdown(labels.SINGLE_TEXT_INTRO)
                build_single_text_tab()

            with gr.TabItem(labels.TAB_BATCH):
                build_batch_tab()

    demo.launch(share=True)
