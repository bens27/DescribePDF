"""
Web UI module for DescribePDF with OpenRouter.

This module implements the Gradio-based web interface for the OpenRouter
provider version of DescribePDF.
"""

import gradio as gr
import os
import tempfile
import logging
import secrets
from typing import Tuple, Optional, Dict, Any, List

from . import config
from . import core
from . import folder_picker
from . import ui_prompts

theme = gr.themes.Soft(
    primary_hue="red",
    secondary_hue="rose",
    spacing_size="lg",
)

# Provider selector labels mapped to the internal provider ids used by core
PROVIDER_LABELS = {
    "OpenRouter": "openrouter",
    "Baidu Qianfan (direct)": "qianfan",
}

def _provider_from_label(label: str) -> str:
    return PROVIDER_LABELS.get(label, "openrouter")

def _label_from_provider(provider: str) -> str:
    for label, pid in PROVIDER_LABELS.items():
        if pid == provider:
            return label
    return "OpenRouter"

def convert_pdf_to_descriptive_markdown(
    pdf_file_obj: Optional[gr.File],
    ui_provider: str,
    ui_api_key: str,
    ui_qianfan_key: str,
    ui_vlm_model: str,
    ui_lang: str, 
    ui_use_md: bool, 
    ui_use_sum: bool, 
    ui_sum_model: str,
    ui_page_selection: str,
    ui_include_desc: bool,
    ui_include_trans: bool,
    ui_summary_output: bool,
    ui_prompt_vlm_base: str,
    ui_prompt_vlm_markdown: str,
    ui_prompt_vlm_summary: str,
    ui_prompt_vlm_full: str,
    ui_prompt_vlm_transcribe: str,
    ui_prompt_summary: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True)
) -> Tuple[str, gr.update, Optional[str]]:
    """
    Convert a PDF file to detailed page-by-page Markdown descriptions using Vision-Language Models.
    
    This function processes the uploaded PDF, analyzing the visual and textual content of each page
    using OpenRouter's Vision-Language Models (VLMs). It generates rich, contextual descriptions in
    Markdown format that capture both the visual elements and text content of the document, making
    the PDF accessible and searchable in contexts where traditional text extraction would fail.
    
    Args:
        pdf_file_obj: Gradio File object for the uploaded PDF
        ui_provider: Provider label from the Settings tab
        ui_api_key: OpenRouter API key from UI
        ui_qianfan_key: Baidu Qianfan API key from UI
        ui_vlm_model: VLM model name from UI (e.g., qwen/qwen2.5-vl-72b-instruct)
        ui_lang: Output language for descriptions (e.g., English, Spanish)
        ui_use_md: Whether to use Markitdown for enhanced text extraction
        ui_use_sum: Whether to generate a document summary for context
        ui_sum_model: Summary model name from UI (e.g., google/gemini-2.5-flash-preview)
        ui_page_selection: Optional page selection string (e.g., "1,3,5-10")
        ui_prompt_vlm_base: Per-run override for the base VLM prompt template
        ui_prompt_vlm_markdown: Per-run override for the VLM + Markitdown prompt template
        ui_prompt_vlm_summary: Per-run override for the VLM + summary prompt template
        ui_prompt_vlm_full: Per-run override for the VLM + Markitdown + summary prompt template
        ui_prompt_summary: Per-run override for the document summary prompt template
        progress: Gradio progress tracker
        
    Returns:
        Tuple containing:
        - str: Status message indicating success or failure
        - gr.update: Download button update with the result file
        - Optional[str]: Markdown result content
    """
    # Validate input file
    if pdf_file_obj is None:
        return "Please upload a PDF file.", gr.update(value=None, visible=False), None

    # Load environment config
    env_config = config.get_config()

    # Prepare configuration for this run
    provider = _provider_from_label(ui_provider)
    api_key = ui_api_key.strip() if ui_api_key.strip() else env_config.get("openrouter_api_key")
    qianfan_key = ui_qianfan_key.strip() if ui_qianfan_key.strip() else env_config.get("qianfan_api_key")

    current_run_config: Dict[str, Any] = {
        "provider": provider,
        "openrouter_api_key": api_key,
        "qianfan_api_key": qianfan_key,
        "vlm_model": ui_vlm_model,
        "output_language": ui_lang,
        "use_markitdown": ui_use_md,
        "use_summary": ui_use_sum,
        "summary_llm_model": ui_sum_model if ui_sum_model else env_config.get("or_summary_model"),
        "page_selection": ui_page_selection.strip() if ui_page_selection.strip() else None,
        "include_descriptions": ui_include_desc,
        "include_transcription": ui_include_trans,
        "summary_in_output": ui_summary_output,
        "custom_prompts": ui_prompts.get_custom_prompts([
            ui_prompt_vlm_base, ui_prompt_vlm_markdown, ui_prompt_vlm_summary,
            ui_prompt_vlm_full, ui_prompt_vlm_transcribe, ui_prompt_summary
        ])
    }

    # Validate the key for the selected provider
    if provider == "openrouter" and not current_run_config.get("openrouter_api_key"):
        error_msg = "Error: OpenRouter API Key is missing. Provide it in the Settings tab or set OPENROUTER_API_KEY in the .env file."
        logging.error(error_msg)
        return error_msg, gr.update(value=None, visible=False), None
    if provider == "qianfan" and not current_run_config.get("qianfan_api_key"):
        error_msg = "Error: Baidu Qianfan API Key is missing. Provide it in the Settings tab or set QIANFAN_API_KEY in the .env file."
        logging.error(error_msg)
        return error_msg, gr.update(value=None, visible=False), None

    # Create progress callback for Gradio
    def progress_callback_gradio(progress_value: float, status: str) -> None:
        """
        Update Gradio progress bar with current progress and status message.
        
        Args:
            progress_value (float): Progress value between 0.0 and 1.0
            status (str): Current status message to display
        """
        clamped_progress = max(0.0, min(1.0, progress_value))
        progress(clamped_progress, desc=status)
        logging.info(f"Progress: {status} ({clamped_progress*100:.1f}%)")

    # Run the conversion
    status_message, result_markdown = core.convert_pdf_to_markdown(
        pdf_file_obj.name,
        current_run_config,
        progress_callback_gradio
    )

    # Handle the download file
    if result_markdown:
        try:
            # Get base filename from the uploaded PDF
            base_name = os.path.splitext(os.path.basename(pdf_file_obj.name))[0]
            download_filename = f"{base_name}_description.md"
            
            # Create a temporary file with a random component to avoid collisions
            random_suffix = secrets.token_hex(4)
            temp_dir = tempfile.gettempdir()
            download_filepath = os.path.join(temp_dir, f"{base_name}_{random_suffix}.md")

            # Write markdown result to the temporary file
            with open(download_filepath, "w", encoding="utf-8") as md_file:
                md_file.write(result_markdown)
                
            logging.info(f"Markdown result saved to temporary file for download: {download_filepath}")
            download_button_update = gr.update(value=download_filepath, visible=True, label=f"Download '{download_filename}'")

        except Exception as e:
            logging.error(f"Error creating temporary file for download: {e}")
            status_message += " (Error creating download file)"
            download_button_update = gr.update(value=None, visible=False)
    else:
        download_button_update = gr.update(value=None, visible=False)

    return (
        status_message,
        download_button_update,
        result_markdown if result_markdown else ""
    )

def save_settings(
    ui_provider: str,
    ui_api_key: str,
    ui_qianfan_key: str,
    ui_vlm_model: str,
    ui_lang: str,
    ui_use_md: bool,
    ui_use_sum: bool,
    ui_sum_model: str,
    ui_page_selection: str,
    ui_include_desc: bool,
    ui_include_trans: bool,
    ui_summary_output: bool
) -> str:
    """
    Persist the Settings tab values as defaults for future sessions.

    API keys are only saved when their field is non-empty; leaving one blank
    keeps whatever key is already stored.
    """
    values = {
        "DESCRIBEPDF_PROVIDER": _provider_from_label(ui_provider),
        "DEFAULT_OR_VLM_MODEL": ui_vlm_model,
        "DEFAULT_OR_SUMMARY_MODEL": ui_sum_model,
        "DEFAULT_LANGUAGE": ui_lang,
        "DEFAULT_USE_MARKITDOWN": str(bool(ui_use_md)).lower(),
        "DEFAULT_USE_SUMMARY": str(bool(ui_use_sum)).lower(),
        "DEFAULT_PAGE_SELECTION": ui_page_selection.strip(),
        "DEFAULT_INCLUDE_DESCRIPTIONS": str(bool(ui_include_desc)).lower(),
        "DEFAULT_INCLUDE_TRANSCRIPTION": str(bool(ui_include_trans)).lower(),
        "DEFAULT_SUMMARY_IN_OUTPUT": str(bool(ui_summary_output)).lower()
    }
    key_note = " API key fields left blank keep their stored keys (if any)."
    if ui_api_key and ui_api_key.strip():
        values["OPENROUTER_API_KEY"] = ui_api_key.strip()
    if ui_qianfan_key and ui_qianfan_key.strip():
        values["QIANFAN_API_KEY"] = ui_qianfan_key.strip()
    if "OPENROUTER_API_KEY" in values or "QIANFAN_API_KEY" in values:
        key_note = " Provided API key(s) saved."
    config.save_user_settings(values)
    return f"✅ Settings saved to `{config.USER_ENV_FILE}`.{key_note}"

def reset_settings() -> list:
    """Clear saved settings and repopulate the fields with the defaults."""
    cfg = config.reset_user_settings()
    return [
        gr.update(value=_label_from_provider(cfg.get("provider", "openrouter"))),
        gr.update(value=""),
        gr.update(value=""),
        gr.update(value=cfg.get("or_vlm_model")),
        gr.update(value=cfg.get("output_language")),
        gr.update(value=""),
        gr.update(value=cfg.get("use_markitdown")),
        gr.update(value=cfg.get("use_summary")),
        gr.update(value=cfg.get("or_summary_model")),
        gr.update(value=cfg.get("include_descriptions")),
        gr.update(value=cfg.get("include_transcription")),
        gr.update(value=cfg.get("summary_in_output")),
        "🔄 Saved settings cleared; defaults restored."
    ]

def browse_pdf_folder() -> gr.update:
    """Open a native picker for the batch input folder."""
    path = folder_picker.pick_folder("Choose the folder containing your PDF files")
    return gr.update(value=path) if path else gr.update()

def browse_export_folder() -> gr.update:
    """Open a native picker for the batch export destination."""
    path = folder_picker.pick_folder("Choose the export destination folder")
    return gr.update(value=path) if path else gr.update()

def convert_folder_to_descriptive_markdowns(
    ui_folder_path: str,
    ui_export_path: str,
    ui_overwrite: bool,
    ui_recursive: bool,
    ui_preserve_structure: bool,
    ui_provider: str,
    ui_api_key: str,
    ui_qianfan_key: str,
    ui_vlm_model: str,
    ui_lang: str,
    ui_use_md: bool,
    ui_use_sum: bool,
    ui_sum_model: str,
    ui_page_selection: str,
    ui_include_desc: bool,
    ui_include_trans: bool,
    ui_summary_output: bool,
    ui_prompt_vlm_base: str,
    ui_prompt_vlm_markdown: str,
    ui_prompt_vlm_summary: str,
    ui_prompt_vlm_full: str,
    ui_prompt_vlm_transcribe: str,
    ui_prompt_summary: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True)
) -> Tuple[str, str]:
    """
    Convert every PDF in a folder to Markdown description files using OpenRouter.

    Each PDF produces a .md file with the same name in the chosen export
    folder. Settings and prompt templates from the other tabs apply to every
    file in the batch.

    Args:
        ui_folder_path: Folder containing the PDFs to convert
        ui_export_path: Folder where the .md files are written
        ui_overwrite: Whether to re-convert files whose .md already exists
        ui_recursive: Also convert PDFs in subfolders (all levels)
        ui_preserve_structure: Mirror the subfolder layout in the destination
        ui_provider: Provider label from the Settings tab
        ui_api_key: OpenRouter API key from UI
        ui_qianfan_key: Baidu Qianfan API key from UI
        ui_vlm_model: VLM model name from UI
        ui_lang: Output language for descriptions
        ui_use_md: Whether to use Markitdown for enhanced text extraction
        ui_use_sum: Whether to generate a document summary for context
        ui_sum_model: Summary model name from UI
        ui_page_selection: Optional page selection string applied to every file
        ui_prompt_*: Per-run prompt template overrides
        progress: Gradio progress tracker

    Returns:
        Tuple containing:
        - str: Status message
        - str: Markdown report of per-file outcomes
    """
    if not ui_folder_path or not ui_folder_path.strip():
        return "Please enter the folder containing your PDF files.", ""
    if not ui_export_path or not ui_export_path.strip():
        return "Please enter an export destination folder.", ""

    # Load environment config
    env_config = config.get_config()
    provider = _provider_from_label(ui_provider)
    api_key = ui_api_key.strip() if ui_api_key.strip() else env_config.get("openrouter_api_key")
    qianfan_key = ui_qianfan_key.strip() if ui_qianfan_key.strip() else env_config.get("qianfan_api_key")

    current_run_config: Dict[str, Any] = {
        "provider": provider,
        "openrouter_api_key": api_key,
        "qianfan_api_key": qianfan_key,
        "vlm_model": ui_vlm_model,
        "output_language": ui_lang,
        "use_markitdown": ui_use_md,
        "use_summary": ui_use_sum,
        "summary_llm_model": ui_sum_model if ui_sum_model else env_config.get("or_summary_model"),
        "page_selection": ui_page_selection.strip() if ui_page_selection.strip() else None,
        "include_descriptions": ui_include_desc,
        "include_transcription": ui_include_trans,
        "summary_in_output": ui_summary_output,
        "custom_prompts": ui_prompts.get_custom_prompts([
            ui_prompt_vlm_base, ui_prompt_vlm_markdown, ui_prompt_vlm_summary,
            ui_prompt_vlm_full, ui_prompt_vlm_transcribe, ui_prompt_summary
        ])
    }

    if provider == "openrouter" and not current_run_config.get("openrouter_api_key"):
        error_msg = "Error: OpenRouter API Key is missing. Provide it in the Settings tab or set OPENROUTER_API_KEY in the .env file."
        logging.error(error_msg)
        return error_msg, ""
    if provider == "qianfan" and not current_run_config.get("qianfan_api_key"):
        error_msg = "Error: Baidu Qianfan API Key is missing. Provide it in the Settings tab or set QIANFAN_API_KEY in the .env file."
        logging.error(error_msg)
        return error_msg, ""

    def progress_callback_gradio(progress_value: float, status: str) -> None:
        clamped_progress = max(0.0, min(1.0, progress_value))
        progress(clamped_progress, desc=status)
        logging.info(f"Progress: {status} ({clamped_progress*100:.1f}%)")

    summary, results = core.convert_folder_to_markdown(
        ui_folder_path,
        ui_export_path,
        current_run_config,
        progress_callback_gradio,
        overwrite=ui_overwrite,
        recursive=ui_recursive,
        preserve_structure=ui_preserve_structure
    )

    report = "\n".join(f"- **{name}**: {outcome}" for name, outcome in results)
    return summary, report

def create_ui() -> gr.Blocks:
    """
    Create and return the Gradio interface for OpenRouter.
    
    This function sets up a Gradio web interface with tabs for PDF conversion
    and configuration. It loads initial settings from the environment config
    and provides UI components for adjusting settings for each conversion run.
    
    Returns:
        gr.Blocks: Configured Gradio interface ready to be launched
    """
    # Load initial config from environment
    initial_env_config = config.get_config()

    # Define suggested model lists and languages
    suggested_vlms: List[str] = [
        "qwen/qwen2.5-vl-72b-instruct",
        "qwen/qwen3-vl-32b-instruct",
        "google/gemini-3.5-flash",
        "mistralai/mistral-medium-3-5"
    ]

    suggested_llms: List[str] = [
        "google/gemini-3.5-flash",
        "anthropic/claude-sonnet-4.6",
        "mistralai/mistral-medium-3-5"
    ]
    
    suggested_languages: List[str] = [
        "English", "Spanish", "French", "German", 
        "Chinese", "Japanese", "Italian", 
        "Portuguese", "Russian", "Korean"
    ]

    # Set initial values from config
    initial_vlm = initial_env_config.get("or_vlm_model")
    initial_llm = initial_env_config.get("or_summary_model")
    initial_lang = initial_env_config.get("output_language")
    initial_use_md = initial_env_config.get("use_markitdown")
    initial_use_sum = initial_env_config.get("use_summary")
    initial_include_desc = initial_env_config.get("include_descriptions")
    initial_include_trans = initial_env_config.get("include_transcription")
    initial_summary_output = initial_env_config.get("summary_in_output")
    
    has_env_api_key = bool(initial_env_config.get("openrouter_api_key"))

    # Create the Gradio interface
    with gr.Blocks(title="DescribePDF", theme=theme) as iface:
        gr.Markdown("<center><img src='https://davidlms.github.io/DescribePDF/assets/poster.png' alt='Describe PDF Logo' width='600px'/></center>")
        gr.Markdown(
            """<div style="display: flex;align-items: center;justify-content: center">
            [<a href="https://davidlms.github.io/DescribePDF/">Project Page</a>] | [<a href="https://github.com/DavidLMS/describepdf">Github</a>]</div>
            """
        )
        gr.Markdown(
            "DescribePDF is an open-source tool designed to convert PDF files into detailed page-by-page descriptions in Markdown format using Vision-Language Models (VLMs). Unlike traditional PDF extraction tools that focus on replicating the text layout, DescribePDF generates rich, contextual descriptions of each page's content, making it perfect for visually complex documents like catalogs, scanned documents, and presentations."
            "\n\n"
            "Upload a PDF, adjust settings, and click 'Describe'. "
        )

        with gr.Tabs():
            # Generate tab
            with gr.TabItem("Generate", id=0):
                with gr.Row():
                    with gr.Column(scale=1):
                        pdf_input = gr.File(
                            label="Upload PDF", 
                            file_types=['.pdf'], 
                            type="filepath"
                        )
                        convert_button = gr.Button(
                            "Describe", 
                            variant="primary"
                        )
                        progress_output = gr.Textbox(
                            label="Progress", 
                            interactive=False, 
                            lines=2
                        )
                        download_button = gr.File(
                            label="Download Markdown", 
                            visible=False, 
                            interactive=False
                        )

                    with gr.Column(scale=2):
                        markdown_output = gr.Markdown(label="Result (Markdown)")

            # Batch conversion tab
            with gr.TabItem("Batch", id=3):
                gr.Markdown(
                    "Convert every PDF in a folder. Each `name.pdf` produces `name.md` in the "
                    "export folder — filenames are kept unchanged. Settings and prompt templates "
                    "from the other tabs apply to the whole batch."
                )
                with gr.Row():
                    batch_folder_input = gr.Textbox(
                        label="PDF Folder",
                        placeholder="/path/to/folder/with/pdfs",
                        info="Folder containing the PDF files to convert (top level only)",
                        scale=5
                    )
                    batch_folder_browse = gr.Button("📂 Browse…", scale=1)
                with gr.Row():
                    batch_export_input = gr.Textbox(
                        label="Export Destination",
                        placeholder="/path/to/output/folder",
                        info="Folder where the .md files are written (created if missing)",
                        scale=5
                    )
                    batch_export_browse = gr.Button("📂 Browse…", scale=1)
                with gr.Row():
                    batch_recursive_checkbox = gr.Checkbox(
                        label="Include subfolders (all levels)",
                        value=False,
                        info="Also convert PDFs found in subfolders of the PDF folder"
                    )
                    batch_structure_checkbox = gr.Checkbox(
                        label="Preserve subfolder structure",
                        value=False,
                        info="Mirror the subfolder layout in the export destination; when off, all .md files land in the destination root"
                    )
                batch_overwrite_checkbox = gr.Checkbox(
                    label="Overwrite existing .md files",
                    value=False,
                    info="When unchecked, PDFs whose .md already exists in the destination are skipped"
                )
                batch_button = gr.Button("Describe Folder", variant="primary")
                batch_progress_output = gr.Textbox(
                    label="Progress",
                    interactive=False,
                    lines=2
                )
                batch_results_output = gr.Markdown(label="Results")

            # Configuration tab
            with gr.TabItem("Settings", id=1):
                gr.Markdown(
                    "Adjust settings for the *next* generation. Use **Save as My Defaults** below "
                    "to keep them across restarts."
                )
                provider_input = gr.Radio(
                    label="Provider",
                    choices=list(PROVIDER_LABELS.keys()),
                    value=_label_from_provider(initial_env_config.get("provider", "openrouter")),
                    info="Where to send the model calls. Baidu Qianfan (direct) uses your Baidu account for models not on OpenRouter (e.g. qianfan-ocr-fast)."
                )
                api_key_input = gr.Textbox(
                    label="OpenRouter API Key" + (" (set in .env)" if has_env_api_key else ""),
                    type="password",
                    placeholder="Enter an API key here to override the one in .env" if has_env_api_key else "Enter your OpenRouter API key",
                    value=""
                )
                qianfan_key_input = gr.Textbox(
                    label="Baidu Qianfan API Key" + (" (set in .env)" if initial_env_config.get("qianfan_api_key") else ""),
                    type="password",
                    placeholder="Enter your Baidu Qianfan API key (only needed for the Baidu Qianfan provider)",
                    value=""
                )
                vlm_model_input = gr.Dropdown(
                    label="VLM Model",
                    choices=suggested_vlms,
                    value=initial_vlm,
                    allow_custom_value=True,
                    info="Select or type the model name for the chosen provider (OpenRouter slug, or a Qianfan model like qianfan-ocr-fast)"
                )
                output_language_input = gr.Dropdown(
                    label="Output Language", 
                    choices=suggested_languages,
                    value=initial_lang,
                    allow_custom_value=True,
                    info="Select or type the desired output language (e.g., English, Spanish)"
                )
                page_selection_input = gr.Textbox(
                    label="Page Selection (Optional)", 
                    value="",
                    placeholder="Example: 1,3,5-10,15 (leave empty for all pages)",
                    info="Specify individual pages or ranges to process"
                )
                gr.Markdown("**Output content** — choose what the generated Markdown contains:")
                with gr.Row():
                    include_desc_checkbox = gr.Checkbox(
                        label="Page descriptions",
                        value=initial_include_desc,
                        info="VLM-generated description of each page"
                    )
                    include_trans_checkbox = gr.Checkbox(
                        label="Direct transcription",
                        value=initial_include_trans,
                        info="Verbatim page text: extracted locally with MarkItDown when reliable; the model is only called for scanned or image-heavy pages"
                    )
                    summary_output_checkbox = gr.Checkbox(
                        label="Document summary",
                        value=initial_summary_output,
                        info="Include an LLM-generated summary of the whole document at the top of the output"
                    )
                with gr.Row():
                    use_markitdown_checkbox = gr.Checkbox(
                        label="Use Markitdown for extra text context",
                        value=initial_use_md
                    )
                    use_summary_checkbox = gr.Checkbox(
                        label="Use PDF summary for augmented context (requires extra LLM call)",
                        value=initial_use_sum
                    )
                summary_llm_model_input = gr.Dropdown(
                    label="LLM Model for Summary",
                    choices=suggested_llms,
                    value=initial_llm,
                    allow_custom_value=True,
                    info="Select or type the OpenRouter LLM model name for summaries"
                )
                with gr.Row():
                    save_settings_button = gr.Button("Save as My Defaults", variant="primary")
                    reset_settings_button = gr.Button("Reset Saved Settings")
                settings_status = gr.Markdown("")

            # Prompt templates tab
            with gr.TabItem("Prompts", id=2):
                prompt_editors = ui_prompts.build_prompts_tab()

        # Connect UI components
        conversion_inputs = [
            pdf_input, provider_input, api_key_input, qianfan_key_input, vlm_model_input, output_language_input,
            use_markitdown_checkbox, use_summary_checkbox, summary_llm_model_input, page_selection_input,
            include_desc_checkbox, include_trans_checkbox, summary_output_checkbox
        ] + prompt_editors
        conversion_outputs = [
            progress_output, download_button, markdown_output
        ]
        convert_button.click(
            fn=convert_pdf_to_descriptive_markdown,
            inputs=conversion_inputs,
            outputs=conversion_outputs
        )

        batch_folder_browse.click(fn=browse_pdf_folder, inputs=[], outputs=[batch_folder_input])
        batch_export_browse.click(fn=browse_export_folder, inputs=[], outputs=[batch_export_input])

        save_settings_button.click(
            fn=save_settings,
            inputs=[
                provider_input, api_key_input, qianfan_key_input, vlm_model_input,
                output_language_input, use_markitdown_checkbox, use_summary_checkbox,
                summary_llm_model_input, page_selection_input,
                include_desc_checkbox, include_trans_checkbox, summary_output_checkbox
            ],
            outputs=[settings_status]
        )
        reset_settings_button.click(
            fn=reset_settings,
            inputs=[],
            outputs=[
                provider_input, api_key_input, qianfan_key_input, vlm_model_input,
                output_language_input, page_selection_input, use_markitdown_checkbox,
                use_summary_checkbox, summary_llm_model_input,
                include_desc_checkbox, include_trans_checkbox, summary_output_checkbox,
                settings_status
            ]
        )

        batch_button.click(
            fn=convert_folder_to_descriptive_markdowns,
            inputs=[
                batch_folder_input, batch_export_input, batch_overwrite_checkbox,
                batch_recursive_checkbox, batch_structure_checkbox,
                provider_input, api_key_input, qianfan_key_input, vlm_model_input, output_language_input,
                use_markitdown_checkbox, use_summary_checkbox, summary_llm_model_input,
                page_selection_input, include_desc_checkbox, include_trans_checkbox, summary_output_checkbox
            ] + prompt_editors,
            outputs=[batch_progress_output, batch_results_output]
        )

    return iface

def launch_app() -> None:
    """
    Start the application from the command line.
    
    This function creates the Gradio UI and launches it.
    """
    app: gr.Blocks = create_ui()
    app.launch()
    
if __name__ == "__main__":
    launch_app()