"""Transform one format to other format"""

from typing import Sequence
from markdownify import markdownify
from langchain_core.documents import Document
from langchain_community.document_transformers import MarkdownifyTransformer

def transform_html_to_markdown(htmls: Sequence[Document] | str, strips: Sequence[str]) -> str:
    if isinstance(htmls, str):
        htmls = [htmls]
    results = []
