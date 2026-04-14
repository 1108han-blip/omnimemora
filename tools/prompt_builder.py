"""
prompt_builder.py - Final Prompt Constructor
==============================================
根据 OmniMemora 返回的 packed_context 构造传给 agent CLI 的最终 prompt。
"""


def build_final_prompt(query: str, packed_context: str) -> str:
    """
    若 packed_context 非空，拼接为：
        [Context]
        <packed_context>

        [Task]
        <query>

    否则直接返回原始 query。
    """
    if packed_context and packed_context.strip():
        return (
            "[Context]\n"
            f"{packed_context}\n"
            "\n"
            "[Task]\n"
            f"{query}"
        )
    return query
