"""
Web UI module for DescribePDF with Ollama.

This module implements the Gradio-based web interface for the Ollama
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
from . import ollama_client
from . import ui_prompts

theme = gr.themes.Soft(
    primary_hue="red",
    secondary_hue="rose",
    spacing_size="lg",
)

def convert_pdf_to_descriptive_markdown(
    pdf_file_obj: Optional[gr.File], 
    ollama_endpoint: str, 
    ui_vlm_model: str, 
    ui_lang: str, 
    ui_use_md: bool, 
    ui_use_sum: bool, 
    ui_sum_model: str,
    ui_page_selection: str,
    ui_prompt_vlm_base: str,
    ui_prompt_vlm_markdown: str,
    ui_prompt_vlm_summary: str,
    ui_prompt_vlm_full: str,
    ui_prompt_summary: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True)
) -> Tuple[str, gr.update, Optional[str]]:
    """
    Convert a PDF file to detailed page-by-page Markdown descriptions using local Ollama Vision-Language Models.
    
    This function processes the uploaded PDF, analyzing the visual and textual content of each page
    using locally hosted Vision-Language Models (VLMs) through Ollama. It generates rich, contextual 
    descriptions in Markdown format that capture both the visual elements and text content of the document, 
    making the PDF accessible and searchable in contexts where traditional text extraction would fail.
    
    Unlike the OpenRouter version, this function utilizes local models running through Ollama, 
    providing privacy and eliminating the need for API keys, but potentially with different model options
    and performance characteristics.
    
    Args:
        pdf_file_obj: Gradio File object for the uploaded PDF
        ollama_endpoint: Ollama server endpoint URL (e.g., http://localhost:11434)
        ui_vlm_model: VLM model name from UI (e.g., llama3.2-vision)
        ui_lang: Output language for descriptions (e.g., English, Spanish)
        ui_use_md: Whether to use Markitdown for enhanced text extraction
        ui_use_sum: Whether to generate a document summary for context
        ui_sum_model: Summary model name from UI (e.g., qwen2.5)
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

    # Check Ollama availability
    if not ollama_client.check_ollama_availability(ollama_endpoint):
        error_msg = f"Error: Could not connect to Ollama at {ollama_endpoint}. Make sure it is running."
        logging.error(error_msg)
        return error_msg, gr.update(value=None, visible=False), None

    # Prepare configuration for this run
    current_run_config: Dict[str, Any] = {
        "provider": "ollama",
        "ollama_endpoint": ollama_endpoint,
        "vlm_model": ui_vlm_model,
        "output_language": ui_lang,
        "use_markitdown": ui_use_md,
        "use_summary": ui_use_sum,
        "summary_llm_model": ui_sum_model,
        "page_selection": ui_page_selection.strip() if ui_page_selection.strip() else None,
        "custom_prompts": ui_prompts.get_custom_prompts([
            ui_prompt_vlm_base, ui_prompt_vlm_markdown, ui_prompt_vlm_summary,
            ui_prompt_vlm_full, ui_prompt_summary
        ])
    }

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

def convert_folder_to_descriptive_markdowns(
    ui_folder_path: str,
    ui_export_path: str,
    ui_overwrite: bool,
    ollama_endpoint: str,
    ui_vlm_model: str,
    ui_lang: str,
    ui_use_md: bool,
    ui_use_sum: bool,
    ui_sum_model: str,
    ui_page_selection: str,
    ui_prompt_vlm_base: str,
    ui_prompt_vlm_markdown: str,
    ui_prompt_vlm_summary: str,
    ui_prompt_vlm_full: str,
    ui_prompt_summary: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True)
) -> Tuple[str, str]:
    """
    Convert every PDF in a folder to Markdown description files using local Ollama models.

    Each PDF produces a .md file with the same name in the chosen export
    folder. Settings and prompt templates from the other tabs apply to every
    file in the batch.

    Args:
        ui_folder_path: Folder containing the PDFs to convert
        ui_export_path: Folder where the .md files are written
        ui_overwrite: Whether to re-convert files whose .md already exists
        ollama_endpoint: Ollama server endpoint URL
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

    # Check Ollama availability
    if not ollama_client.check_ollama_availability(ollama_endpoint):
        error_msg = f"Error: Could not connect to Ollama at {ollama_endpoint}. Make sure it is running."
        logging.error(error_msg)
        return error_msg, ""

    current_run_config: Dict[str, Any] = {
        "provider": "ollama",
        "ollama_endpoint": ollama_endpoint,
        "vlm_model": ui_vlm_model,
        "output_language": ui_lang,
        "use_markitdown": ui_use_md,
        "use_summary": ui_use_sum,
        "summary_llm_model": ui_sum_model,
        "page_selection": ui_page_selection.strip() if ui_page_selection.strip() else None,
        "custom_prompts": ui_prompts.get_custom_prompts([
            ui_prompt_vlm_base, ui_prompt_vlm_markdown, ui_prompt_vlm_summary,
            ui_prompt_vlm_full, ui_prompt_summary
        ])
    }

    def progress_callback_gradio(progress_value: float, status: str) -> None:
        clamped_progress = max(0.0, min(1.0, progress_value))
        progress(clamped_progress, desc=status)
        logging.info(f"Progress: {status} ({clamped_progress*100:.1f}%)")

    summary, results = core.convert_folder_to_markdown(
        ui_folder_path,
        ui_export_path,
        current_run_config,
        progress_callback_gradio,
        overwrite=ui_overwrite
    )

    report = "\n".join(f"- **{name}**: {outcome}" for name, outcome in results)
    return summary, report

def create_ui() -> gr.Blocks:
    """
    Create and return the Gradio interface for Ollama.
    
    This function sets up a Gradio web interface with tabs for PDF conversion
    and configuration. It loads initial settings from the environment config
    and provides UI components for adjusting settings for each conversion run.
    
    Returns:
        gr.Blocks: Configured Gradio interface ready to be launched
    """
    # Load initial config from environment
    initial_env_config = config.get_config()

    # Define suggested model lists and languages
    suggested_vlms: List[str] = ["llama3.2-vision"]
    suggested_llms: List[str] = ["qwen2.5", "llama3.2"]
    suggested_languages: List[str] = [
        "English", "Spanish", "French", "German", 
        "Chinese", "Japanese", "Italian", 
        "Portuguese", "Russian", "Korean"
    ]

    # Set initial values from config
    initial_endpoint = initial_env_config.get("ollama_endpoint", "http://localhost:11434")
    initial_vlm = initial_env_config.get("ollama_vlm_model", "llama3.2-vision")
    initial_llm = initial_env_config.get("ollama_summary_model", "qwen2.5")
    initial_lang = initial_env_config.get("output_language", "English")
    initial_use_md = initial_env_config.get("use_markitdown", False)
    initial_use_sum = initial_env_config.get("use_summary", False)

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

            # Configuration tab
            # Batch conversion tab
            with gr.TabItem("Batch", id=3):
                gr.Markdown(
                    "Convert every PDF in a folder. Each `name.pdf` produces `name.md` in the "
                    "export folder — filenames are kept unchanged. Settings and prompt templates "
                    "from the other tabs apply to the whole batch."
                )
                batch_folder_input = gr.Textbox(
                    label="PDF Folder",
                    placeholder="/path/to/folder/with/pdfs",
                    info="Folder containing the PDF files to convert (top level only)"
                )
                batch_export_input = gr.Textbox(
                    label="Export Destination",
                    placeholder="/path/to/output/folder",
                    info="Folder where the .md files are written (created if missing)"
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

            with gr.TabItem("Settings", id=1):
                gr.Markdown(
                    "Adjust settings for the *next* generation. These settings are **not** saved. "
                    "Defaults are controlled by the `.env` file."
                )
                ollama_endpoint_input = gr.Textbox(
                    label="Ollama Endpoint",
                    value=initial_endpoint,
                    placeholder="http://localhost:11434",
                    info="URL of your Ollama server"
                )
                vlm_model_input = gr.Dropdown(
                    label="VLM Model", 
                    choices=suggested_vlms,
                    value=initial_vlm,
                    allow_custom_value=True,
                    info="Select or type the Ollama vision model name"
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
                    info="Select or type the Ollama LLM model name for summaries"
                )

            # Prompt templates tab
            with gr.TabItem("Prompts", id=2):
                prompt_editors = ui_prompts.build_prompts_tab()

        # Connect UI components
        conversion_inputs = [
            pdf_input, ollama_endpoint_input, vlm_model_input, output_language_input,
            use_markitdown_checkbox, use_summary_checkbox, summary_llm_model_input, page_selection_input
        ] + prompt_editors
        conversion_outputs = [
            progress_output, download_button, markdown_output
        ]
        convert_button.click(
            fn=convert_pdf_to_descriptive_markdown,
            inputs=conversion_inputs,
            outputs=conversion_outputs
        )

        batch_button.click(
            fn=convert_folder_to_descriptive_markdowns,
            inputs=[
                batch_folder_input, batch_export_input, batch_overwrite_checkbox,
                ollama_endpoint_input, vlm_model_input, output_language_input,
                use_markitdown_checkbox, use_summary_checkbox, summary_llm_model_input,
                page_selection_input
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