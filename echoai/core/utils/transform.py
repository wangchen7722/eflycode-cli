"""Transform one format to other format"""

from typing import Sequence

from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_core.documents import Document
from markdownify import markdownify


def transform_html_to_markdown(htmls: Sequence[Document] | str, strips: Sequence[str]) -> str:
    if isinstance(htmls, str):
        htmls = [htmls]
    results = []
