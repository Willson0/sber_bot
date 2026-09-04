from dataclasses import dataclass

@dataclass
class TextAnswer:
    success: bool = None
    error_text: str = None

    answer: str = None
    token_consumed: int = 0
