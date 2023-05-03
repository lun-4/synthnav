import os
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class GenerationSettings:
    """GPT model settings"""

    max_new_tokens: int
    do_sample: bool
    temperature: float
    top_p: float
    typical_p: int
    repetition_penalty: float
    top_k: int
    min_length: int
    no_repeat_ngram_size: int
    num_beams: int
    penalty_alpha: int
    length_penalty: int
    early_stopping: bool
    add_bos_token: bool
    truncation_length: int
    ban_eos_token: bool
    skip_special_tokens: bool
    stopping_strings: List[str]

    @classmethod
    def llama_defaults(cls):
        """Specific to how I use LLaMa models"""
        return cls(
            max_new_tokens=100,
            do_sample=True,
            temperature=0.75,
            top_p=0.73,
            typical_p=1,
            repetition_penalty=1.18,
            top_k=40,
            min_length=0,
            no_repeat_ngram_size=0,
            num_beams=1,
            penalty_alpha=0,
            length_penalty=1,
            early_stopping=False,
            add_bos_token=True,
            truncation_length=2048,
            ban_eos_token=False,
            skip_special_tokens=True,
            stopping_strings=[],
        )


@dataclass
class Config:
    server_address: str
    debug: bool = False
    mock: bool = False
    mock_node_amount: Optional[int] = None
    generation_settings: GenerationSettings = field(
        default_factory=GenerationSettings.llama_defaults
    )

    @classmethod
    def from_environ(cls, server_address: Optional[str] = None) -> "Config":
        self = cls(server_address or os.environ["SERVER_ADDR"])
        self.debug = bool(os.environ.get("DEBUG"))
        self.mock = bool(os.environ.get("MOCK"))
        maybe_mock_node_amount = os.environ.get("MOCK_NODE_AMOUNT")
        if maybe_mock_node_amount:
            self.mock_node_amount = int(maybe_mock_node_amount)
        return self

    @classmethod
    async def from_database(cls, db) -> "Config":
        async with db.execute("select server_address from config") as cursor:
            row = await cursor.fetchone()
        return cls(row[0])
