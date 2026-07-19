"""
CI helper: trigger a MarkItDown-enabled conversion against a running app.

Used by the Windows build workflow to prove MarkItDown extraction works
inside the frozen bundle (its magika/pdfminer data files load lazily, so
only a real conversion exercises them). The API key is deliberately invalid:
extraction happens before the VLM call, and the caller greps the app log for
'Markitdown context extracted'.

Usage: python ci_markitdown_smoke.py <base_url> <pdf_path>
"""

import sys

from gradio_client import Client, handle_file


def main() -> None:
    base_url, pdf_path = sys.argv[1], sys.argv[2]
    client = Client(base_url, verbose=False)
    try:
        client.predict(
            handle_file(pdf_path),
            "OpenRouter", "sk-or-invalid-ci-key", "",
            "mistralai/mistral-medium-3-5", "English",
            True, False,  # use_markitdown ON, summary off
            "google/gemini-2.5-flash-preview", "",
            True, False, False,  # descriptions on, transcription off, summary-in-output off
            "", "", "", "", "", "",
            api_name="/convert_pdf_to_descriptive_markdown",
        )
    except Exception as e:
        print(f"predict raised (expected with the invalid key): {e}")
    print("conversion triggered")


if __name__ == "__main__":
    main()
