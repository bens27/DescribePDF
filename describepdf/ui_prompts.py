"""
Shared UI components for viewing and editing prompt templates.

This module builds the "Prompts" tab used by both web UIs. Edits made in the
tab apply to the next conversion run; "Save as My Defaults" persists them as
user overrides. The factory templates shipped with the application are never
modified and can always be restored.
"""

import gradio as gr
from typing import Dict, List, Tuple

from . import config

# Fixed ordering of templates as they appear in the tab and are passed to the
# conversion function.
PROMPT_ORDER: List[str] = ["vlm_base", "vlm_markdown", "vlm_summary", "vlm_full", "vlm_transcribe", "summary"]

# key -> (label, description of when it is used and its placeholders)
PROMPT_INFO: Dict[str, Tuple[str, str]] = {
    "vlm_base": (
        "Page Description (base)",
        "Used for each page when neither Markitdown nor summary context is enabled. "
        "Placeholders: [PAGE_NUM], [TOTAL_PAGES], [LANGUAGE]"
    ),
    "vlm_markdown": (
        "Page Description + Markitdown context",
        "Used when 'Use Markitdown' is enabled. "
        "Placeholders: [PAGE_NUM], [TOTAL_PAGES], [LANGUAGE], [MARKDOWN_CONTEXT]"
    ),
    "vlm_summary": (
        "Page Description + Summary context",
        "Used when 'Use PDF summary' is enabled. "
        "Placeholders: [PAGE_NUM], [TOTAL_PAGES], [LANGUAGE], [SUMMARY_CONTEXT]"
    ),
    "vlm_full": (
        "Page Description + Markitdown + Summary",
        "Used when both Markitdown and summary context are enabled. "
        "Placeholders: [PAGE_NUM], [TOTAL_PAGES], [LANGUAGE], [MARKDOWN_CONTEXT], [SUMMARY_CONTEXT]"
    ),
    "vlm_transcribe": (
        "Direct Transcription (model fallback)",
        "Used when 'Direct transcription' is enabled and a page can't be confidently transcribed by "
        "MarkItDown locally (scanned or image-heavy pages). Placeholders: [PAGE_NUM], [TOTAL_PAGES], [LANGUAGE]"
    ),
    "summary": (
        "Document Summary",
        "Used to generate the document-level summary. Placeholder: [FULL_PDF_TEXT]"
    ),
}


def get_custom_prompts(values: List[str]) -> Dict[str, str]:
    """
    Build the per-run prompt override mapping from the tab's field values.

    Blank fields are omitted so they fall back to the saved defaults.

    Args:
        values: Field values in PROMPT_ORDER order

    Returns:
        Dict[str, str]: Mapping suitable for cfg["custom_prompts"]
    """
    return {
        key: text
        for key, text in zip(PROMPT_ORDER, values)
        if isinstance(text, str) and text.strip()
    }


def build_prompts_tab() -> List[gr.Textbox]:
    """
    Build the contents of the "Prompts" tab inside an open gr.TabItem.

    Returns:
        List[gr.Textbox]: The template editors in PROMPT_ORDER order, for use
        as additional inputs to the conversion function.
    """
    current = config.get_prompts()

    gr.Markdown(
        "Edit the prompt templates used for generation. Changes here apply to the **next** run. "
        "Use **Save as My Defaults** to keep them for future sessions "
        f"(stored in `{config.USER_PROMPTS_DIR}`). "
        "The original templates are always preserved: **Restore Factory Defaults** brings them back at any time. "
        "A blank field falls back to the saved default."
    )

    editors: List[gr.Textbox] = []
    for key in PROMPT_ORDER:
        label, description = PROMPT_INFO[key]
        with gr.Accordion(label, open=False):
            editor = gr.Textbox(
                value=current.get(key, ""),
                label=config.PROMPT_FILES[key],
                info=description,
                lines=10
            )
            editors.append(editor)

    with gr.Row():
        save_button = gr.Button("Save as My Defaults", variant="primary")
        reload_button = gr.Button("Reload Saved Defaults")
        factory_button = gr.Button("Restore Factory Defaults")

    prompts_status = gr.Markdown("")

    def save_defaults(*values: str):
        effective = config.save_user_prompts(dict(zip(PROMPT_ORDER, values)))
        updates = [gr.update(value=effective.get(key, "")) for key in PROMPT_ORDER]
        return updates + [f"✅ Saved. Customized templates are stored in `{config.USER_PROMPTS_DIR}`; "
                          "templates matching the factory version use the factory file."]

    def reload_saved():
        effective = config.reload_prompts()
        updates = [gr.update(value=effective.get(key, "")) for key in PROMPT_ORDER]
        return updates + ["🔄 Reloaded your saved defaults."]

    def restore_factory():
        effective = config.reset_user_prompts()
        updates = [gr.update(value=effective.get(key, "")) for key in PROMPT_ORDER]
        return updates + ["🏭 Factory defaults restored. Your customizations have been removed."]

    save_button.click(fn=save_defaults, inputs=editors, outputs=editors + [prompts_status])
    reload_button.click(fn=reload_saved, inputs=[], outputs=editors + [prompts_status])
    factory_button.click(fn=restore_factory, inputs=[], outputs=editors + [prompts_status])

    # Free-form notes, saved automatically as you type. Kept separate from the
    # prompt templates: the buttons above never modify or reset this field.
    with gr.Accordion("Future Ideas", open=False):
        future_ideas = gr.Textbox(
            value=config.load_future_ideas(),
            label="Notes",
            info="A scratchpad for prompt ideas to try later. Saved automatically; "
                 "not affected by 'Restore Factory Defaults'.",
            lines=8
        )
        future_ideas.change(fn=config.save_future_ideas, inputs=[future_ideas], outputs=[])

    return editors
